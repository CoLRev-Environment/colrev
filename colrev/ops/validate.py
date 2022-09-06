#! /usr/bin/env python
from __future__ import annotations

import itertools
from itertools import chain
from pathlib import Path

import colrev.process
import colrev.record


class Validate(colrev.process.Process):
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:

        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.check,
        )

        self.cpus = 4

    def load_search_records(self, *, bib_file: Path) -> list:

        with open(bib_file, encoding="utf8") as bibtex_file:
            individual_bib_rd = self.review_manager.dataset.load_records_dict(
                load_str=bibtex_file.read()
            )
            for record in individual_bib_rd.values():
                record["colrev_origin"] = bib_file.stem + "/" + record["ID"]

        return list(individual_bib_rd.values())

    def get_search_records(self) -> list:

        search_dir = self.review_manager.search_dir

        records = []
        # records = p_map(self.load_search_records, list(search_dir.glob("*.bib")))
        for search_file in search_dir.glob("*.bib"):
            records.append(self.load_search_records(bib_file=search_file))

        records = list(chain(*records))

        return records

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
            if commit_id == target_commit:
                found_target_commit = True
                continue
            if not found_target_commit:
                continue
            prior_records_dict = self.review_manager.dataset.load_records_dict(
                load_str=filecontents.decode("utf-8")
            )
            break
        return prior_records_dict

    def validate_preparation_changes(
        self, *, records: list[dict], target_commit
    ) -> list:

        prior_records_dict = self.__load_prior_records_dict(target_commit=target_commit)

        self.review_manager.logger.debug("Calculating preparation differences...")
        change_diff = []
        for record_dict in records:
            # input(record)
            if "changed_in_target_commit" not in record_dict:
                continue
            del record_dict["changed_in_target_commit"]
            del record_dict["colrev_status"]
            for cur_record_link in record_dict["colrev_origin"].split(";"):
                prior_records = [
                    x
                    for x in prior_records_dict.values()
                    if cur_record_link in x["colrev_origin"].split(",")
                ]
                for prior_record_dict in prior_records:
                    similarity = colrev.record.Record.get_record_similarity(
                        record_a=colrev.record.Record(data=record_dict),
                        record_b=colrev.record.Record(data=prior_record_dict),
                    )
                    # change_diff.append([record["ID"], cur_record_link, similarity])
                    change_diff.append([prior_record_dict, record_dict, similarity])

        change_diff = [[e1, e2, sim] for [e1, e2, sim] in change_diff if sim < 1]

        # sort according to similarity
        change_diff.sort(key=lambda x: x[2], reverse=True)

        return change_diff

    def validate_merging_changes(
        self, *, records: list[dict], target_commit: str
    ) -> list:

        prior_records_dict = self.__load_prior_records_dict(target_commit=target_commit)

        change_diff = []
        merged_records = False
        for record in records:
            if "changed_in_target_commit" not in record:
                continue
            del record["changed_in_target_commit"]
            if ";" in record["colrev_origin"]:
                merged_records = True
                els = record["colrev_origin"].split(";")
                duplicate_el_pairs = list(itertools.combinations(els, 2))
                for el_1, el_2 in duplicate_el_pairs:
                    record_1 = [
                        x
                        for x in prior_records_dict.values()
                        if el_1 == x["colrev_origin"]
                    ]
                    record_2 = [
                        x
                        for x in prior_records_dict.values()
                        if el_2 == x["colrev_origin"]
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

        # sort according to similarity
        change_diff.sort(key=lambda x: x[2], reverse=True)

        return change_diff

    def load_records(self, *, target_commit: str = None) -> list[dict]:

        if target_commit is None:
            self.review_manager.logger.info("Loading data...")
            records = self.review_manager.dataset.load_records_dict()
            for record_dict in records.values():
                record_dict.update(changed_in_target_commit="True")
            return list(records.values())

        self.review_manager.logger.info("Loading data from history...")
        git_repo = self.review_manager.dataset.get_repo()

        records_file_relative = self.review_manager.dataset.RECORDS_FILE_RELATIVE

        revlist = (
            (
                commit.hexsha,
                (commit.tree / str(records_file_relative)).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(records_file_relative))
        )
        found = False
        for commit, filecontents in list(revlist):
            if found:  # load the records_file_relative in the following commit
                prior_records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=filecontents.decode("utf-8")
                )
                break
            if commit == target_commit:
                records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=filecontents.decode("utf-8")
                )
                found = True

        # determine which records have been changed (prepared or merged)
        # in the target_commit
        for record in records_dict.values():
            prior_record = [
                rec for id, rec in prior_records_dict.items() if id == record["ID"]
            ][0]
            # Note: the following is an exact comparison of all fields
            if record != prior_record:
                record.update(changed_in_target_commit="True")

        return list(records_dict.values())

    def validate_properties(self, *, target_commit: str = None) -> None:
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
                    scope = "merge"
                else:
                    scope = "unspecified"
        return scope

    def main(
        self, *, scope: str, properties: bool = False, target_commit: str = ""
    ) -> list:

        if properties:
            self.validate_properties(target_commit=target_commit)
            return []

        # extension: filter for changes of contributor (git author)
        records = self.load_records(target_commit=target_commit)

        if target_commit == "" and "unspecified" == scope:
            scope = self.__set_scope_based_on_target_commit(target_commit=target_commit)

        if scope in ["prepare", "all"]:
            validation_details = self.validate_preparation_changes(
                records=records, target_commit=target_commit
            )

        if scope in ["merge", "all"]:
            validation_details = self.validate_merging_changes(
                records=records, target_commit=target_commit
            )

        # if 'unspecified' == scope:
        #     git_repo = self.review_manager.dataset.get_repo()
        #     t = git_repo.head.commit.tree
        #     print(git_repo.git.diff('HEAD~1'))
        #     validation_details = {}
        #     input('stop')

        return validation_details


if __name__ == "__main__":
    pass
