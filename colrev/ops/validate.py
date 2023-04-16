#! /usr/bin/env python
"""Validates commits in a CoLRev project."""
from __future__ import annotations

import datetime
import re
import typing
from pathlib import Path
from typing import Optional

from tqdm import tqdm

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record


class Validate(colrev.operation.Operation):
    """Validate changes"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
        )

        self.cpus = 4

    def __load_prior_records_dict(self, *, target_commit: str) -> dict:
        git_repo = self.review_manager.dataset.get_repo()

        revlist = (
            (
                commit.hexsha,
                (
                    commit.tree / str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                ).data_stream.read(),
            )
            for commit in git_repo.iter_commits(
                paths=str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
            )
        )

        found_target_commit = False
        for commit_id, filecontents in list(revlist):
            if target_commit:
                if commit_id == target_commit:
                    found_target_commit = True
                    continue
                if not found_target_commit:
                    continue
            elif not found_target_commit:
                # To skip the same commit
                found_target_commit = True
                continue
            prior_records_dict = self.review_manager.dataset.load_records_dict(
                load_str=filecontents.decode("utf-8")
            )
            return prior_records_dict
        return {}

    def validate_preparation_changes(
        self, *, records: list[dict], prior_records_dict: dict
    ) -> list:
        """Validate preparation changes"""

        self.review_manager.logger.debug("Calculating preparation differences...")
        change_diff = []
        covered_ids = []
        for record_dict in records:
            if "changed_in_target_commit" not in record_dict:
                continue
            del record_dict["changed_in_target_commit"]
            prescreen_excluded = (
                colrev.record.RecordState.rev_prescreen_excluded
                == record_dict["colrev_status"]
            )
            del record_dict["colrev_status"]
            for cur_record_link in record_dict["colrev_origin"]:
                prior_records = [
                    x
                    for x in prior_records_dict.values()
                    if cur_record_link in x["colrev_origin"]
                ]
                for prior_record_dict in prior_records:
                    change_score = colrev.record.Record.get_record_change_score(
                        record_a=colrev.record.Record(data=record_dict),
                        record_b=colrev.record.Record(data=prior_record_dict),
                    )
                    if record_dict["ID"] not in covered_ids:
                        change_diff.append(
                            {
                                "prior_record_dict": prior_record_dict,
                                "record_dict": record_dict,
                                "change_score": change_score,
                                "prescreen_exclusion_mark": prescreen_excluded,
                            }
                        )
                        covered_ids.append(record_dict["ID"])

        # sort according to similarity
        change_diff.sort(key=lambda x: x["change_score"], reverse=True)

        return change_diff

    def validate_dedupe_changes(
        self, *, records: list[dict], target_commit: str
    ) -> list:
        """Validate dedupe changes"""

        # pylint: disable=too-many-locals
        # pylint: disable=too-many-branches

        # at some point, we may allow users to validate
        # all duplicates/non-duplicates (across commits)

        prior_records_dict = self.__load_prior_records_dict(target_commit=target_commit)

        change_diff = []
        merged_records = False
        for record in records:
            if "changed_in_target_commit" not in record:
                continue
            del record["changed_in_target_commit"]

            if len(record["colrev_origin"]) == 1:
                continue
            merged_records = True

            merged_records_list = []

            for prior_record in prior_records_dict.values():
                if len(prior_record["colrev_origin"]) == 1:
                    continue
                if any(
                    o in record["colrev_origin"] for o in prior_record["colrev_origin"]
                ):
                    merged_records_list.append(prior_record)

            if len(merged_records_list) < 2:
                # merged records not found
                continue

            reference_record = merged_records_list.pop(0)
            # Note : should usually be only one merged_rec (but multiple-merges are possible)
            for merged_rec in merged_records_list:
                change_score = colrev.record.Record.get_record_change_score(
                    record_a=colrev.record.Record(data=reference_record),
                    record_b=colrev.record.Record(data=merged_rec),
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

        merge_candidates_file = Path("merge_candidates_file.txt")

        with open(merge_candidates_file, "w", encoding="utf-8") as file:
            for ref_rec_dict in tqdm(records):
                ref_rec = colrev.record.Record(data=ref_rec_dict)
                for comp_rec_dict in reversed(records):
                    # Note : due to symmetry, we only need one part of the matrix
                    if ref_rec_dict["ID"] == comp_rec_dict["ID"]:
                        break
                    comp_rec = colrev.record.Record(data=comp_rec_dict)
                    similarity = colrev.record.Record.get_record_similarity(
                        record_a=ref_rec, record_b=comp_rec
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

        # sort according to similarity
        change_diff.sort(key=lambda x: x["change_score"], reverse=True)

        return change_diff

    def load_changed_records(
        self, *, target_commit: Optional[str] = None
    ) -> list[dict]:
        """Load the records that were changed in the target commit"""
        if target_commit is None:
            self.review_manager.logger.info("Loading data...")
            records = self.review_manager.dataset.load_records_dict()
            for record_dict in records.values():
                record_dict.update(changed_in_target_commit="True")
            return list(records.values())

        self.review_manager.logger.info("Loading data from history...")
        dataset = self.review_manager.dataset
        changed_records = dataset.get_changed_records(target_commit=target_commit)

        return changed_records

    def validate_properties(self, *, commit: str) -> dict:
        """Validate properties"""

        # option: --history: check all preceding commits (create a list...)

        git_repo = self.review_manager.dataset.get_repo()

        cur_sha = git_repo.head.commit.hexsha
        cur_branch = git_repo.active_branch.name

        validation_details: typing.Dict[str, bool] = {}

        if git_repo.is_dirty() and not commit == cur_sha:
            self.review_manager.logger.error(
                "Error: Need a clean repository to validate properties "
                "of prior commit"
            )
            return validation_details

        if not commit == cur_sha:
            self.review_manager.logger.info(f"Check out target_commit = {commit}")
            git_repo.git.checkout(commit)

        ret = self.review_manager.check_repo()
        if 0 == ret["status"]:
            validation_details["record_traceability"] = True
            validation_details["consistency"] = True

        else:
            validation_details["record_traceability"] = False
            validation_details["consistency"] = False

        completeness_condition = self.review_manager.get_completeness_condition()
        if completeness_condition:
            validation_details["completeness"] = True

        else:
            validation_details["completeness"] = False

        git_repo.git.checkout(cur_branch, force=True)

        return validation_details

    def __set_scope_based_on_target_commit(self, *, target_commit: str) -> str:
        # pylint: disable=too-many-branches

        if not target_commit:
            target_commit = self.review_manager.dataset.get_last_commit_sha()

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
            if commit_id == target_commit:
                if "colrev prep" in msg:
                    scope = "prepare"
                elif "colrev dedupe" in msg:
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
            # use them to calculate the validation_details
            records: typing.Dict[str, typing.Dict] = {}
            hist_records: typing.Dict[str, typing.Dict] = {}
            for recs in self.review_manager.dataset.load_records_from_history(
                commit_sha=target_commit
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
                scope = "dedupe"

        return scope

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
                    "ID": rid,
                    "coder1": str(record_dict["colrev_status"]),
                    "coder2": str(other_branch_records[rid]["colrev_status"]),
                    "reconciled": str(records_reconciled[rid]["colrev_status"]),
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

    def validate_merge_changes(self) -> list:
        """Validate merge changes (reconciliation between branches)"""

        merge_validation = []

        git_repo = self.review_manager.dataset.get_repo()

        revlist = git_repo.iter_commits(
            paths=str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
        )

        for commit in list(revlist):
            if len(commit.parents) <= 1:
                continue

            if not any(x in commit.message for x in ["prescreen", "screen"]):
                continue

            records_branch_1 = self.review_manager.dataset.load_records_dict(
                load_str=(
                    commit.parents[0].tree
                    / str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                )
                .data_stream.read()
                .decode("utf-8")
            )
            records_branch_2 = self.review_manager.dataset.load_records_dict(
                load_str=(
                    commit.parents[1].tree
                    / str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                )
                .data_stream.read()
                .decode("utf-8")
            )
            records_reconciled = self.review_manager.dataset.load_records_dict(
                load_str=(
                    commit.tree / str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                )
                .data_stream.read()
                .decode("utf-8")
            )
            if "screen" in commit.message or "prescreen" in commit.message:
                prescreen_validation = self.validate_merge_prescreen_screen(
                    commit_sha=commit.hexsha,
                    current_branch_records=records_branch_1,
                    other_branch_records=records_branch_2,
                    records_reconciled=records_reconciled,
                )
                merge_validation.append(prescreen_validation)

        return merge_validation

    def __get_target_commit(self, *, scope: str) -> str:
        """Get the commit from commit sha or tree hash"""

        commit = ""
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
            except ValueError:
                for commit_candidate in git_repo.iter_commits():
                    if str(commit_candidate.tree) == scope:
                        commit = commit_candidate.hexsha
                        break
                    valid_options.append(str(commit_candidate.tree))

                if commit == "":
                    # pylint: disable=raise-missing-from
                    raise colrev_exceptions.ParameterError(
                        parameter="validate.scope", value=scope, options=valid_options
                    )

        if not re.match(r"[0-9a-f]{5,40}", commit):
            raise colrev_exceptions.ParameterError(
                parameter="commit",
                value=scope,
                options=[x.hexsha for x in git_repo.iter_commits()],
            )
        return commit

    def __deduplicated_records(
        self, *, records: list[dict], prior_records_dict: dict
    ) -> bool:
        return {",".join(sorted(x)) for x in [r["colrev_origin"] for r in records]} != {
            ",".join(sorted(x))
            for x in [r["colrev_origin"] for r in prior_records_dict.values()]
        }

    def __get_contributor_validation(self, *, contributor: str) -> dict:
        validation_details: typing.Dict[str, typing.Any] = {"contributor_commits": []}
        valid_options = []
        git_repo = self.review_manager.dataset.get_repo()
        for commit in git_repo.iter_commits():
            if any(
                x == contributor
                for x in [
                    commit.author.email,
                    commit.author.name,
                    commit.committer.email,
                    commit.committer.name,
                ]
            ):
                commit_date = datetime.datetime.fromtimestamp(commit.committed_date)
                validation_details["contributor_commits"].append(
                    {
                        commit.hexsha: {
                            "msg": commit.message.split("\n", maxsplit=1)[0],
                            "date": commit_date,
                            "author": commit.author.name,
                            "author_email": commit.author.email,
                            "committer": commit.committer.name,
                            "committer_email": commit.committer.email,
                            "validate": f"colrev validate {commit.hexsha}",
                        }
                    }
                )

            if not self.review_manager.verbose_mode:
                if "script" in commit.author.name:
                    continue
            if commit.author.name not in valid_options:
                valid_options.append(commit.author.name)
            if commit.author.email not in valid_options:
                valid_options.append(commit.author.email)

        if not validation_details["contributor_commits"]:
            raise colrev_exceptions.ParameterError(
                parameter="validate.contributor",
                value=contributor,
                options=valid_options,
            )
        return validation_details

    def __get_relative_commit(self, target_commit: str) -> str:
        git_repo = self.review_manager.dataset.get_repo()

        relative_to_head = 0
        for commit in git_repo.iter_commits():
            if target_commit == commit.hexsha:
                return f"HEAD~{relative_to_head}"
            relative_to_head += 1

        return target_commit

    def main(
        self,
        *,
        scope: str,
        filter_setting: str,
        properties: bool = False,
    ) -> dict:
        """Validate a commit (main entrypoint)"""

        if (
            "HEAD" not in scope
            and not re.match(r"[0-9a-f]{5,40}", scope)
            and "." != scope
        ):
            return self.__get_contributor_validation(contributor=scope)

        target_commit = self.__get_target_commit(scope=scope)

        validation_details: typing.Dict[str, typing.Any] = {}
        if properties:
            validation_details["properties"] = self.validate_properties(
                commit=target_commit
            )
            return validation_details

        if filter_setting == "all":
            filter_setting = self.__set_scope_based_on_target_commit(
                target_commit=target_commit
            )
        if filter_setting == "general":
            validation_details["general"] = {
                "commit": target_commit,
                "commit_relative": self.__get_relative_commit(
                    target_commit=target_commit
                ),
            }
            return validation_details

        self.review_manager.logger.info(f"Filter: {filter_setting} changes")

        # extension: filter_setting for changes of contributor (git author)
        records = self.load_changed_records(target_commit=target_commit)
        prior_records_dict = self.__load_prior_records_dict(target_commit=target_commit)

        if filter_setting in ["prepare", "all"]:
            validation_details["prep"] = self.validate_preparation_changes(
                records=records, prior_records_dict=prior_records_dict
            )
        if filter_setting in ["dedupe", "all"]:
            # Note : the if-statement avoids time-consuming procedures when the
            # origin-sets have not changed (no duplicates merged)
            if self.__deduplicated_records(
                records=records, prior_records_dict=prior_records_dict
            ):
                validation_details["dedupe"] = self.validate_dedupe_changes(
                    records=records, target_commit=target_commit
                )

        # Note : merge for git branches
        if filter_setting == "merge":
            validation_details["merge"] = self.validate_merge_changes()

        return validation_details


if __name__ == "__main__":
    pass
