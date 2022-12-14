#! /usr/bin/env python
"""Validates commits in a CoLRev project."""
from __future__ import annotations

import itertools

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
        self, *, records: list[dict], target_commit: str
    ) -> list:
        """Validate preparation changes"""
        prior_records_dict = self.__load_prior_records_dict(target_commit=target_commit)

        self.review_manager.logger.debug("Calculating preparation differences...")
        change_diff = []
        for record_dict in records:
            # input(record)
            if "changed_in_target_commit" not in record_dict:
                continue
            del record_dict["changed_in_target_commit"]
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
                    change_diff.append([prior_record_dict, record_dict, change_score])

        # sort according to similarity
        change_diff.sort(key=lambda x: x[2], reverse=True)

        return change_diff

    def validate_dedupe_changes(
        self, *, records: list[dict], target_commit: str
    ) -> list:
        """Validate dedupe changes"""

        # pylint: disable=too-many-locals

        prior_records_dict = self.__load_prior_records_dict(target_commit=target_commit)

        # https://github.com/geritwagner/colrev/issues/57
        # change_diff should also have a better data structure
        change_diff = []
        merged_records = False
        for record in records:
            # https://github.com/geritwagner/colrev/issues/57
            # allow users to validate all duplicates/non-duplicates (across commits)
            if "changed_in_target_commit" not in record:
                continue
            del record["changed_in_target_commit"]
            if ";" in record["colrev_origin"]:
                merged_records = True
                duplicate_el_pairs = list(
                    itertools.combinations(record["colrev_origin"], 2)
                )
                for el_1, el_2 in duplicate_el_pairs:
                    record_1 = [
                        x
                        for x in prior_records_dict.values()
                        if any(el_1 == co for co in x["colrev_origin"])
                    ]
                    record_2 = [
                        x
                        for x in prior_records_dict.values()
                        if any(el_2 == co for co in x["colrev_origin"])
                    ]

                    similarity = colrev.record.Record.get_record_similarity(
                        record_a=colrev.record.Record(data=record_1[0]),
                        record_b=colrev.record.Record(data=record_2[0]),
                    )
                    change_diff.append([record_1[0], record_2[0], similarity])

        change_diff = [[e1, e2, sim] for [e1, e2, sim] in change_diff if sim < 1]

        if 0 == len(change_diff):
            if merged_records:
                self.review_manager.logger.info("No substantial differences found.")
            else:
                self.review_manager.logger.info("No merged records")

        # https://github.com/geritwagner/colrev/issues/57
        # create the dataframes (like in the simple merge)
        # Similarly: create dataframes of the latest prepared records
        # to check FP merges efficiently
        with open(
            "merge_candidates_file.txt", "w", encoding="utf-8"
        ) as merge_candidates_file:
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

                        merge_candidates_file.write(ref_rec.format_bib_style())
                        merge_candidates_file.write("\n")
                        merge_candidates_file.write(comp_rec.format_bib_style())
                        merge_candidates_file.write("\n")
                        merge_candidates_file.write(
                            f"colrev dedupe -m {ref_rec_dict['ID']},{comp_rec_dict['ID']}\n\n"
                        )

        # sort according to similarity
        change_diff.sort(key=lambda x: x[2], reverse=True)

        return change_diff

    def load_changed_records(self, *, target_commit: str = None) -> list[dict]:
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

    def validate_properties(self, *, target_commit: str = None) -> None:
        """Validate properties"""

        # option: --history: check all preceding commits (create a list...)

        git_repo = self.review_manager.dataset.get_repo()

        cur_sha = git_repo.head.commit.hexsha
        cur_branch = git_repo.active_branch.name
        self.review_manager.logger.info(
            f" Current commit: {cur_sha} (branch {cur_branch})"
        )

        if not target_commit:
            target_commit = cur_sha
        if git_repo.is_dirty() and not target_commit == cur_sha:
            self.review_manager.logger.error(
                "Error: Need a clean repository to validate properties "
                "of prior commit"
            )
            return
        if not target_commit == cur_sha:
            self.review_manager.logger.info(
                f"Check out target_commit = {target_commit}"
            )
            git_repo.git.checkout(target_commit)

        ret = self.review_manager.check_repo()
        if 0 == ret["status"]:
            self.review_manager.logger.info(
                " Traceability of records".ljust(32, " ") + "YES (validated)"
            )
            self.review_manager.logger.info(
                " Consistency (based on hooks)".ljust(32, " ") + "YES (validated)"
            )
        else:
            self.review_manager.logger.error(
                "Traceability of records".ljust(32, " ") + "NO"
            )
            self.review_manager.logger.error(
                "Consistency (based on hooks)".ljust(32, " ") + "NO"
            )

        completeness_condition = self.review_manager.get_completeness_condition()
        if completeness_condition:
            self.review_manager.logger.info(
                " Completeness of iteration".ljust(32, " ") + "YES (validated)"
            )
        else:
            self.review_manager.logger.error(
                "Completeness of iteration".ljust(32, " ") + "NO"
            )

        git_repo.git.checkout(cur_branch, force=True)

    def get_commit_from_tree_hash(self, tree_hash: str) -> str:
        """Get the commit sha from a tree hash"""
        valid_options = []
        for commit in self.review_manager.dataset.get_repo().iter_commits():
            if str(commit.tree) == tree_hash:
                return commit.hexsha
            valid_options.append(str(commit.tree))
        raise colrev_exceptions.ParameterError(
            parameter="validate.tree_hash", value=tree_hash, options=valid_options
        )

    def __set_scope_based_on_target_commit(self, *, target_commit: str) -> str:

        target_commit = self.review_manager.dataset.get_last_commit_sha()

        git_repo = self.review_manager.dataset.get_repo()

        revlist = list(
            (
                commit.hexsha,
                commit.message,
            )
            for commit in git_repo.iter_commits(paths="status.yaml")
        )
        for commit_id, msg in revlist:
            if commit_id == target_commit:
                if "colrev prep" in msg:
                    scope = "prepare"
                elif "colrev dedupe" in msg:
                    scope = "dedupe"
                else:
                    scope = "unspecified"
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

            # self.review_manager.p_printer.pprint(merge_validation)

        return merge_validation

    def main(
        self, *, scope: str, properties: bool = False, target_commit: str = ""
    ) -> list:
        """Validate a commit (main entrypoint)"""
        if properties:
            self.validate_properties(target_commit=target_commit)
            return []

        # extension: filter for changes of contributor (git author)
        records = self.load_changed_records(target_commit=target_commit)

        if target_commit == "" and "unspecified" == scope:
            scope = self.__set_scope_based_on_target_commit(target_commit=target_commit)

        validation_details = []
        if scope in ["prepare", "all"]:
            validation_details += self.validate_preparation_changes(
                records=records, target_commit=target_commit
            )

        if scope in ["dedupe", "all"]:
            validation_details += self.validate_dedupe_changes(
                records=records, target_commit=target_commit
            )

        if scope == "merge":
            validation_details += self.validate_merge_changes()

        # if 'unspecified' == scope:
        #     git_repo = self.review_manager.dataset.get_repo()
        #     t = git_repo.head.commit.tree
        #     print(git_repo.git.diff('HEAD~1'))
        #     validation_details = {}
        #     input('stop')

        return validation_details


if __name__ == "__main__":
    pass
