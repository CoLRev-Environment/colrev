#! /usr/bin/env python
"""Validates commits in a CoLRev project."""
from __future__ import annotations

import datetime
import re
import typing
from pathlib import Path

from tqdm import tqdm

import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState


class Validate(colrev.process.operation.Operation):
    """Validate changes"""

    type = OperationsType.check

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
        )

        self.cpus = 4

    def _load_prior_records_dict(self, *, commit_sha: str) -> dict:
        """If commit is "": return the last commited version of records"""
        git_repo = self.review_manager.dataset.get_repo()
        # Ensure the path uses forward slashes, which is compatible with Git's path handling
        records_file_path = self.review_manager.paths.RECORDS_FILE_GIT
        revlist = (
            (
                commit_i.hexsha,
                (commit_i.tree / records_file_path).data_stream.read(),
            )
            for commit_i in git_repo.iter_commits(
                paths=str(self.review_manager.paths.RECORDS_FILE)
            )
        )

        found_target_commit = False
        for commit_id, filecontents in list(revlist):
            if commit_sha:
                if commit_id == commit_sha:
                    found_target_commit = True
                    continue
                if not found_target_commit:
                    continue
            elif not found_target_commit:
                # To skip the same commit
                found_target_commit = True
                continue
            prior_records_dict = colrev.loader.load_utils.loads(
                load_string=filecontents.decode("utf-8"),
                implementation="bib",
                logger=self.review_manager.logger,
            )

            return prior_records_dict
        return {}

    def _get_prep_prescreen_exclusions(self, records: dict) -> list:
        self.review_manager.logger.debug("Get prescreen exclusions...")

        target_commit = self._get_target_commit(scope="HEAD~1")
        prior_records_dict = self._load_prior_records_dict(commit_sha=target_commit)
        prep_prescreen_exclusions = []
        for record_dict in records.values():
            for prior_record_dict in prior_records_dict.values():
                if set(record_dict[Fields.ORIGIN]).intersection(
                    set(prior_record_dict[Fields.ORIGIN])
                ):
                    if (
                        prior_record_dict[Fields.STATUS]
                        != RecordState.rev_prescreen_excluded
                        and record_dict[Fields.STATUS]
                        == RecordState.rev_prescreen_excluded
                    ):
                        prep_prescreen_exclusions.append(record_dict)

        return prep_prescreen_exclusions

    def _get_change_diff(self, *, records: dict, origin_records: dict) -> list:
        self.review_manager.logger.debug("Calculating preparation differences...")

        change_diff = []
        for record_dict in records.values():

            origin_changes = []
            for origin in record_dict[Fields.ORIGIN]:
                origin_record = origin_records[origin]

                change_score = colrev.record.record.Record.get_record_change_score(
                    colrev.record.record.Record(record_dict),
                    colrev.record.record.Record(origin_record),
                )

                origin_record["change_score"] = change_score
                origin_changes.append(origin_record)

            origin_changes.sort(key=lambda x: x["change_score"], reverse=False)

            change_diff.append(
                {
                    "record_dict": record_dict,
                    "change_score_max": (
                        max(
                            origin_change["change_score"]
                            for origin_change in origin_changes
                        )
                        if origin_changes
                        else 0
                    ),
                    "origins": origin_changes,
                }
            )

        # sort according to similarity
        change_diff.sort(key=lambda x: x["change_score_max"], reverse=True)
        return change_diff

    def _validate_prep_changes(self, *, report: dict) -> None:
        """Validate preparation changes"""

        self.review_manager.logger.debug("Load records...")

        load_operation = self.review_manager.get_load_operation()
        origin_records = {}
        for source in load_operation.load_active_sources(include_md=True):
            if not source.search_source.filename.is_file():
                continue
            load_operation.setup_source_for_load(source, select_new_records=False)
            for origin_record in source.search_source.source_records_list:
                origin_records[origin_record[Fields.ORIGIN][0]] = origin_record

        records = self.review_manager.dataset.load_records_dict()

        report["prep_prescreen_exclusions"] = self._get_prep_prescreen_exclusions(
            records
        )
        report["prep"] = self._get_change_diff(
            records=records, origin_records=origin_records
        )

    def _export_merge_candidates_file(self, records: list[dict]) -> None:
        merge_candidates_file = Path("data/dedupe/merge_candidates_file.txt")
        merge_candidates_file.parent.mkdir(exist_ok=True, parents=True)

        with open(merge_candidates_file, "w", encoding="utf-8") as file:
            for ref_rec_dict in tqdm(records):
                ref_rec = colrev.record.record.Record(ref_rec_dict)
                for comp_rec_dict in reversed(records):
                    # Note : due to symmetry, we only need one part of the matrix
                    if ref_rec_dict[Fields.ID] == comp_rec_dict[Fields.ID]:
                        break
                    comp_rec = colrev.record.record.Record(comp_rec_dict)
                    similarity = colrev.record.record.Record.get_record_similarity(
                        ref_rec, comp_rec
                    )

                    if similarity > 0.95:
                        print(f"{ref_rec_dict['ID']}-{comp_rec_dict['ID']}")

                        file.write(ref_rec.format_bib_style())
                        file.write("\n")
                        file.write(comp_rec.format_bib_style())
                        file.write("\n")
                        file.write(
                            f"colrev dedupe -m {ref_rec_dict['ID']},{comp_rec_dict['ID']}\n\n"
                        )

        if merge_candidates_file.read_text(encoding="utf-8") == "":
            merge_candidates_file.unlink()

    def _validate_dedupe_changes(self, *, report: dict, commit_sha: str) -> None:
        """Validate dedupe changes"""

        # at some point, we may allow users to validate
        # all duplicates/non-duplicates (across commits)

        # if self._gids_conflict(main_record=main_record, dupe_record=dupe_record):
        #     self.review_manager.logger.info(
        #         "Prevented merge with conflicting global IDs: "
        #         f"{main_record.data[Fields.ID]} - {dupe_record.data[Fields.ID]}"
        #     )
        #     return True

        # def _gids_conflict(
        #     self, *, main_record: colrev.record.record.Record,
        #               sdupe_record: colrev.record.record.Record
        # ) -> bool:
        #     gid_conflict = False
        #     if Fields.DOI in main_record.data and Fields.DOI in dupe_record.data:
        #         doi_main = main_record.data.get(Fields.DOI, "a").replace("\\", "")
        #         doi_dupe = dupe_record.data.get(Fields.DOI, "b").replace("\\", "")
        #         if doi_main != doi_dupe:
        #             gid_conflict = True

        #     return gid_conflict

        records = self._load_changed_records(commit_sha=commit_sha)

        prior_records_dict = self._load_prior_records_dict(commit_sha=commit_sha)
        # Note : the if-statement avoids time-consuming procedures when the
        # origin-sets have not changed (no duplicates merged)
        if not self._deduplicated_records(
            records=records, prior_records_dict=prior_records_dict
        ):
            report["dedupe"] = []
            return

        change_diff = []
        merged_records = False
        for record in records:
            if "changed_in_target_commit" not in record:
                continue
            del record["changed_in_target_commit"]

            if len(record[Fields.ORIGIN]) == 1:
                continue
            merged_records = True

            merged_records_list = []

            for prior_record in prior_records_dict.values():
                if len(prior_record[Fields.ORIGIN]) == 1:
                    continue
                if any(o in record[Fields.ORIGIN] for o in prior_record[Fields.ORIGIN]):
                    merged_records_list.append(prior_record)

            if len(merged_records_list) < 2:
                # merged records not found
                continue

            reference_record = merged_records_list.pop(0)
            # Note : should usually be only one merged_rec (but multiple-merges are possible)
            for merged_rec in merged_records_list:
                change_score = colrev.record.record.Record.get_record_change_score(
                    colrev.record.record.Record(reference_record),
                    colrev.record.record.Record(merged_rec),
                )
                change_diff.append(
                    {
                        "record": record,
                        "prior_record_a": reference_record,
                        "prior_record_b": merged_rec,
                        "change_score": change_score,
                    }
                )

        change_diff = [
            element for element in change_diff if element["change_score"] < 1
        ]
        if 0 == len(change_diff):
            if merged_records:
                self.review_manager.logger.info("No substantial differences found.")
            else:
                self.review_manager.logger.info("No merged records")

        self._export_merge_candidates_file(records)

        # sort according to similarity
        change_diff.sort(key=lambda x: x["change_score"], reverse=True)

        report["dedupe"] = change_diff

    def _get_changed_records(self, *, target_commit: str) -> typing.List[dict]:
        """Get the records that changed in a selected commit"""

        dataset = self.review_manager.dataset
        git_repo = dataset.get_repo()
        revlist = (
            (
                commit.hexsha,
                (
                    commit.tree / self.review_manager.paths.RECORDS_FILE_GIT
                ).data_stream.read(),
            )
            for commit in git_repo.iter_commits(
                paths=str(self.review_manager.paths.RECORDS_FILE)
            )
        )
        found = False
        records: typing.Dict[str, typing.Any] = {}
        prior_records = {}
        for commit, filecontents in list(revlist):
            if found:  # load the records_file_relative in the following commit
                prior_records = colrev.loader.load_utils.loads(
                    load_string=filecontents.decode("utf-8"),
                    implementation="bib",
                    logger=self.review_manager.logger,
                )
                break
            if commit == target_commit:
                records = colrev.loader.load_utils.loads(
                    load_string=filecontents.decode("utf-8"),
                    implementation="bib",
                    logger=self.review_manager.logger,
                )
                found = True

        # determine which records have been changed (prepared or merged)
        # in the target_commit
        for record in records.values():
            prior_record_l = [
                rec
                for rec in prior_records.values()
                if any(x in record[Fields.ORIGIN] for x in rec[Fields.ORIGIN])
            ]
            if prior_record_l:
                prior_record = prior_record_l[0]
                # Note: the following is an exact comparison of all fields
                if record != prior_record:
                    record.update(changed_in_target_commit="True")

        return list(records.values())

    def _load_changed_records(
        self, *, commit_sha: typing.Optional[str] = None
    ) -> list[dict]:
        """Load the records that were changed in the target commit"""
        if commit_sha is None:
            self.review_manager.logger.info("Loading data...")
            records = self.review_manager.dataset.load_records_dict()
            for record_dict in records.values():
                record_dict.update(changed_in_target_commit="True")
            return list(records.values())

        self.review_manager.logger.info("Loading data from history...")
        changed_records = self._get_changed_records(target_commit=commit_sha)

        return changed_records

    def _validate_properties(self, *, commit_sha: str) -> dict:
        """Validate properties"""

        # option: --history: check all preceding commits (create a list...)

        git_repo = self.review_manager.dataset.get_repo()

        cur_sha = git_repo.head.commit.hexsha
        cur_branch = git_repo.active_branch.name
        report: typing.Dict[str, typing.Any] = {}

        if git_repo.is_dirty() and not commit_sha == cur_sha:
            self.review_manager.logger.error(
                "Error: Need a clean repository to validate properties "
                "of prior commit"
            )
            return {}

        if not commit_sha == cur_sha:
            self.review_manager.logger.info(f"Check out target_commit = {commit_sha}")
            git_repo.git.checkout(commit_sha)

        ret = self.review_manager.check_repo()
        if 0 == ret["status"]:
            report["record_traceability"] = True
            report["consistency"] = True

        else:
            report["record_traceability"] = False
            report["consistency"] = False

        completeness_condition = self.review_manager.get_completeness_condition()
        if completeness_condition:
            report["completeness"] = True

        else:
            report["completeness"] = False

        git_repo.git.checkout(cur_branch, force=True)

        return {"properties": report}

    def _validate_general(self, *, commit_sha: str) -> dict:
        return {
            "general": {
                "commit": commit_sha,
                "commit_relative": self._get_relative_commit(commit_sha=commit_sha),
            }
        }

    def _set_scope_based_on_target_commit(self, *, commit_sha: str) -> str:
        # pylint: disable=too-many-branches

        if not commit_sha:
            commit_sha = self.review_manager.dataset.get_last_commit_sha()

        git_repo = self.review_manager.dataset.get_repo()

        revlist = list(
            (
                commit.hexsha,
                commit.message,
            )
            for commit in git_repo.iter_commits()
        )

        scope = ""
        # Note : simple heuristic: commit messages
        for commit_id, msg in revlist:
            if commit_id == commit_sha:
                if "colrev prep" in msg:
                    scope = "prepare"
                elif "colrev dedupe" in msg:
                    # pylint: disable=colrev-missed-constant-usage
                    scope = "dedupe"
                elif any(
                    x in msg
                    for x in [
                        "colrev init",
                        "colrev load",
                        "colrev pdf-get",
                        "colrev pdf-prep",
                        "colrev screen",
                        "colrev prescreen",
                    ]
                ):
                    scope = "general"
                else:
                    scope = "general"
            if scope != "":
                break

        # Otherwise: compare records
        if scope in ["general"]:
            # detect transition types in the respective commit and
            # use them to calculate the report
            records: typing.Dict[str, typing.Dict] = {}
            hist_records: typing.Dict[str, typing.Dict] = {}
            for recs in self.review_manager.dataset.load_records_from_history(
                commit_sha
            ):
                # continue
                if not records:
                    records = recs
                    continue
                if not hist_records:
                    hist_records = recs
                    break

            # Note : still very simple heuristics...
            if len(records) != len(hist_records):
                # pylint: disable=colrev-missed-constant-usage
                scope = "dedupe"

        return scope

    def _get_filter_setting(
        self, *, filter_setting: str, properties: bool, commit_sha: str, scope: str
    ) -> str:
        if self._is_contributor_validation_condition(scope):
            filter_setting = "contributor"

        elif properties:
            filter_setting = "properties"
        elif filter_setting == "all":
            filter_setting = self._set_scope_based_on_target_commit(
                commit_sha=commit_sha
            )

        self.review_manager.logger.info(f"Filter: {filter_setting} changes")
        return filter_setting

    def validate_merge_prescreen_screen(
        self,
        *,
        commit_sha: str = "CURRENT",
        current_branch_records: dict,
        other_branch_records: dict,
        records_reconciled: dict,
        # current_branch_name: str = "",
        # other_branch_name: str = "",
    ) -> dict:
        """Validate presceen/screen between merged branches"""

        prescreen_validation = {"commit_sha": commit_sha, "prescreen": []}
        for rid, record_dict in current_branch_records.items():
            prescreen_validation["prescreen"].append(  # type: ignore
                {
                    Fields.ID: rid,
                    "coder1": str(record_dict[Fields.STATUS]),
                    "coder2": str(other_branch_records[rid][Fields.STATUS]),
                    "reconciled": str(records_reconciled[rid][Fields.STATUS]),
                }
            )
        prescreen_validation["statistics"] = {  # type: ignore
            "percentage_agreement": len(
                [
                    x
                    for x in prescreen_validation["prescreen"]
                    if x["coder1"] == x["coder2"]  # type: ignore
                ]
            )
            / len(prescreen_validation["prescreen"])
        }
        return prescreen_validation

    def _validate_merge_changes(self) -> dict:
        """Validate merge changes (reconciliation between branches)"""

        merge_validation = []

        git_repo = self.review_manager.dataset.get_repo()

        revlist = git_repo.iter_commits(
            paths=str(self.review_manager.paths.RECORDS_FILE)
        )
        # Ensure the path uses forward slashes, which is compatible with Git's path handling

        for commit in list(revlist):
            if len(commit.parents) <= 1:
                continue

            if not any(x in commit.message for x in ["prescreen", "screen"]):
                continue

            load_str = (
                (commit.parents[0].tree / self.review_manager.paths.RECORDS_FILE_GIT)
                .data_stream.read()
                .decode("utf-8")
            )
            records_branch_1 = colrev.loader.load_utils.loads(
                load_string=load_str,
                implementation="bib",
                logger=self.review_manager.logger,
            )

            load_str = (
                (commit.parents[1].tree / self.review_manager.paths.RECORDS_FILE_GIT)
                .data_stream.read()
                .decode("utf-8")
            )
            records_branch_2 = colrev.loader.load_utils.loads(
                load_string=load_str,
                implementation="bib",
                logger=self.review_manager.logger,
            )

            load_str = (
                (commit.tree / self.review_manager.paths.RECORDS_FILE_GIT)
                .data_stream.read()
                .decode("utf-8")
            )
            records_reconciled = colrev.loader.load_utils.loads(
                load_string=load_str,
                implementation="bib",
                logger=self.review_manager.logger,
            )

            if "screen" in commit.message or "prescreen" in commit.message:
                prescreen_validation = self.validate_merge_prescreen_screen(
                    commit_sha=commit.hexsha,
                    current_branch_records=records_branch_1,
                    other_branch_records=records_branch_2,
                    records_reconciled=records_reconciled,
                )
                merge_validation.append(prescreen_validation)

        return {"merge": merge_validation}

    def _get_target_commit(self, *, scope: str, filter_setting: str = "") -> str:
        """Get the commit from commit sha or tree hash"""

        commit = ""
        if filter_setting == "contributor":
            return commit

        git_repo = self.review_manager.dataset.get_repo()
        if scope in ["HEAD", "."]:
            scope = "HEAD~0"
        if scope.startswith("HEAD~"):
            assert scope.replace("HEAD~", "").isdigit()
            back_count = int(scope.replace("HEAD~", ""))
            for commit_item in git_repo.iter_commits():
                if back_count == 0:
                    commit = commit_item.hexsha
                    break
                back_count -= 1
        else:
            valid_options = []

            try:
                commit_object = git_repo.commit(scope)
                commit = commit_object.hexsha
            except ValueError as exc:
                for commit_candidate in git_repo.iter_commits():
                    if str(commit_candidate.tree) == scope:
                        commit = commit_candidate.hexsha
                        break
                    valid_options.append(str(commit_candidate.tree))

                if commit == "":
                    # pylint: disable=raise-missing-from
                    raise colrev_exceptions.ParameterError(
                        parameter="validate.scope", value=scope, options=valid_options
                    ) from exc

        if not re.match(r"[0-9a-f]{5,40}", commit):
            raise colrev_exceptions.ParameterError(
                parameter="commit",
                value=scope,
                options=[x.hexsha for x in git_repo.iter_commits()],
            )
        return commit

    def _deduplicated_records(
        self, *, records: list[dict], prior_records_dict: dict
    ) -> bool:
        return {",".join(sorted(x)) for x in [r[Fields.ORIGIN] for r in records]} != {
            ",".join(sorted(x))
            for x in [r[Fields.ORIGIN] for r in prior_records_dict.values()]
        }

    def _get_contributor_validation(self, *, scope: str) -> dict:
        report: typing.Dict[str, typing.Any] = {"contributor_commits": []}
        valid_options = []
        git_repo = self.review_manager.dataset.get_repo()
        for commit in git_repo.iter_commits():
            if any(
                x == scope
                for x in [
                    commit.author.email,
                    commit.author.name,
                    commit.committer.email,
                    commit.committer.name,
                ]
            ):
                commit_date = datetime.datetime.fromtimestamp(commit.committed_date)
                report["contributor_commits"].append(
                    {
                        "msg": commit.message.split("\n", maxsplit=1)[0],
                        "date": commit_date,
                        "author": commit.author.name,
                        "author_email": commit.author.email,
                        "commit_sha": commit.hexsha,
                        "committer": commit.committer.name,
                        "committer_email": commit.committer.email,
                        "validate": f"colrev validate {commit.hexsha}",
                    }
                )

            if not self.review_manager.verbose_mode:
                if "script" in commit.author.name:
                    continue
            if commit.author.name not in valid_options:
                valid_options.append(commit.author.name)
            if commit.author.email not in valid_options:
                valid_options.append(commit.author.email)

        if not report["contributor_commits"]:
            raise colrev_exceptions.ParameterError(
                parameter="validate.contributor",
                value=scope,
                options=valid_options,
            )
        return report

    def _get_relative_commit(self, commit_sha: str) -> str:
        git_repo = self.review_manager.dataset.get_repo()

        relative_to_head = 0
        for commit_i in git_repo.iter_commits():
            if commit_sha == commit_i.hexsha:
                return f"HEAD~{relative_to_head}"
            relative_to_head += 1

        return commit_sha

    def _is_contributor_validation_condition(self, scope: str) -> bool:
        return (
            "HEAD" not in scope
            and not re.match(r"[0-9a-f]{5,40}", scope)
            and "." != scope
        )

    @colrev.process.operation.Operation.decorate()
    def main(
        self,
        *,
        scope: str,
        filter_setting: str,
        properties: bool = False,
    ) -> dict:
        """Validate a commit (main entrypoint)"""

        target_commit = self._get_target_commit(
            scope=scope, filter_setting=filter_setting
        )

        filter_setting = self._get_filter_setting(
            filter_setting=filter_setting,
            properties=properties,
            commit_sha=target_commit,
            scope=scope,
        )

        if filter_setting == "general":
            return self._validate_general(commit_sha=target_commit)

        if filter_setting == "contributor":
            return self._get_contributor_validation(scope=scope)

        if filter_setting == "properties":
            return self._validate_properties(commit_sha=target_commit)

        if filter_setting == "merge":  # for git branches (not colrev dedupe)
            return self._validate_merge_changes()

        report: typing.Dict[str, typing.Any] = {}
        if filter_setting in ["prepare", "all"]:
            self._validate_prep_changes(report=report)
        if filter_setting in ["dedupe", "all"]:
            self._validate_dedupe_changes(report=report, commit_sha=target_commit)
        return report
