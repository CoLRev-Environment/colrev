#! /usr/bin/env python
import itertools
import os
import typing
from itertools import chain
from pathlib import Path

import bibtexparser
import dictdiffer
import git
from bashplotlib.histogram import plot_hist
from bibtexparser.customization import convert_to_unicode
from p_tqdm import p_map

from colrev_core.process import Process
from colrev_core.process import ProcessType


class Validate(Process):
    def __init__(self, REVIEW_MANAGER):

        super().__init__(REVIEW_MANAGER, ProcessType.check)

        self.CPUS = self.REVIEW_MANAGER.config["CPUS"]

    def load_search_records(self, bib_file: Path) -> list:

        with open(bib_file, encoding="utf8") as bibtex_file:
            individual_bib_db = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode,
                common_strings=True,
            ).parse_file(bibtex_file, partial=True)
            for record in individual_bib_db.entries:
                record["colrev_origin"] = bib_file.stem + "/" + record["ID"]

        return individual_bib_db.entries

    def get_search_records(self) -> list:

        search_dir = self.REVIEW_MANAGER.paths["SEARCHDIR"]

        records = p_map(self.load_search_records, list(search_dir.glob("*.bib")))
        records = list(chain(*records))

        return records

    def validate_preparation_changes(
        self, records: typing.List[dict], search_records: list
    ) -> None:
        from colrev_core.record import Record

        self.REVIEW_MANAGER.logger.info("Calculating preparation differences...")
        change_diff = []
        for record in records:
            if "changed_in_target_commit" not in record:
                continue
            del record["changed_in_target_commit"]
            del record["colrev_status"]
            # del record['colrev_origin']
            for cur_record_link in record["colrev_origin"].split(";"):
                prior_records = [
                    x
                    for x in search_records
                    if cur_record_link in x["colrev_origin"].split(",")
                ]
                for prior_record in prior_records:
                    similarity = Record.get_record_similarity(
                        Record(record), Record(prior_record)
                    )
                    change_diff.append([record["ID"], cur_record_link, similarity])

        change_diff = [[e1, e2, 1 - sim] for [e1, e2, sim] in change_diff if sim < 1]

        if 0 == len(change_diff):
            self.REVIEW_MANAGER.logger.info("No substantial differences found.")
        else:
            plot_hist(
                [sim for [e1, e2, sim] in change_diff],
                bincount=100,
                xlab=True,
                showSummary=True,
            )

        # sort according to similarity
        change_diff.sort(key=lambda x: x[2], reverse=True)
        input("continue")

        for eid, record_link, difference in change_diff:
            # Escape sequence to clear terminal output for each new comparison
            os.system("cls" if os.name == "nt" else "clear")
            self.REVIEW_MANAGER.logger.info("Record with ID: " + eid)

            self.REVIEW_MANAGER.logger.info(
                "Difference: " + str(round(difference, 4)) + "\n\n"
            )
            record_1 = [x for x in search_records if record_link == x["colrev_origin"]]
            print(Record(record_1[0]))
            record_2 = [x for x in records if eid == x["ID"]]
            print(Record(record_2[0]))

            print("\n\n")
            for diff in list(dictdiffer.diff(record_1, record_2)):
                # Note: may treat fields differently (e.g., status, ID, ...)
                self.REVIEW_MANAGER.pp.pprint(diff)

            if "n" == input("continue (y/n)?"):
                break
            # input('TODO: correct? if not, replace current record with old one')

        return

    def validate_merging_changes(
        self, records: typing.List[dict], search_records: list
    ) -> None:
        from colrev_core.record import Record

        os.system("cls" if os.name == "nt" else "clear")
        self.REVIEW_MANAGER.logger.info(
            "Calculating differences between merged records..."
        )
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
                    record_1 = [x for x in search_records if el_1 == x["colrev_origin"]]
                    record_2 = [x for x in search_records if el_2 == x["colrev_origin"]]

                    similarity = Record.get_record_similarity(
                        Record(record_1[0]), Record(record_2[0])
                    )
                    change_diff.append([el_1, el_2, similarity])

        change_diff = [[e1, e2, 1 - sim] for [e1, e2, sim] in change_diff if sim < 1]

        if 0 == len(change_diff):
            if merged_records:
                self.REVIEW_MANAGER.logger.info("No substantial differences found.")
            else:
                self.REVIEW_MANAGER.logger.info("No merged records")

        # sort according to similarity
        change_diff.sort(key=lambda x: x[2], reverse=True)

        for el_1, el_2, difference in change_diff:
            # Escape sequence to clear terminal output for each new comparison
            os.system("cls" if os.name == "nt" else "clear")

            print(
                "Differences between merged records:" + f" {round(difference, 4)}\n\n"
            )
            record_1 = [x for x in search_records if el_1 == x["colrev_origin"]]
            print(Record(record_1[0]))
            record_2 = [x for x in search_records if el_2 == x["colrev_origin"]]
            print(Record(record_2[0]))

            if "n" == input("continue (y/n)?"):
                break

        return

    def load_records(self, target_commit: str = None) -> typing.List[dict]:

        if target_commit is None:
            self.REVIEW_MANAGER.logger.info("Loading data...")
            records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
            [x.update(changed_in_target_commit="True") for x in records.values()]
            return records.values()

        else:
            self.REVIEW_MANAGER.logger.info("Loading data from history...")
            git_repo = git.Repo()

            MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths[
                "MAIN_REFERENCES_RELATIVE"
            ]

            revlist = (
                (
                    commit.hexsha,
                    (commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read(),
                )
                for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
            )
            found = False
            for commit, filecontents in list(revlist):
                if found:  # load the MAIN_REFERENCES_RELATIVE in the following commit
                    prior_bib_db = bibtexparser.loads(filecontents)
                    break
                if commit == target_commit:
                    bib_db = bibtexparser.loads(filecontents)
                    records = bib_db.entries
                    found = True

            # determine which records have been changed (prepared or merged)
            # in the target_commit
            for record in records:
                prior_record = [
                    x for x in prior_bib_db.entries if x["ID"] == record["ID"]
                ][0]
                # Note: the following is an exact comparison of all fields
                if record != prior_record:
                    record.update(changed_in_target_commit="True")

            return records

    def validate_properties(self, target_commit: str = None) -> None:
        # option: --history: check all preceding commits (create a list...)

        from colrev_core.status import Status

        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()

        cur_sha = git_repo.head.commit.hexsha
        cur_branch = git_repo.active_branch.name
        self.REVIEW_MANAGER.logger.info(
            f" Current commit: {cur_sha} (branch {cur_branch})"
        )

        if not target_commit:
            target_commit = cur_sha
        if git_repo.is_dirty() and not target_commit == cur_sha:
            self.REVIEW_MANAGER.logger.error(
                "Error: Need a clean repository to validate properties "
                "of prior commit"
            )
            return
        if not target_commit == cur_sha:
            self.REVIEW_MANAGER.logger.info(
                f"Check out target_commit = {target_commit}"
            )
            git_repo.git.checkout(target_commit)

        ret = self.REVIEW_MANAGER.check_repo()
        if 0 == ret["status"]:
            self.REVIEW_MANAGER.logger.info(
                " Traceability of records".ljust(32, " ") + "YES (validated)"
            )
            self.REVIEW_MANAGER.logger.info(
                " Consistency (based on hooks)".ljust(32, " ") + "YES (validated)"
            )
        else:
            self.REVIEW_MANAGER.logger.error(
                "Traceability of records".ljust(32, " ") + "NO"
            )
            self.REVIEW_MANAGER.logger.error(
                "Consistency (based on hooks)".ljust(32, " ") + "NO"
            )

        STATUS = Status(self.REVIEW_MANAGER)
        completeness_condition = STATUS.get_completeness_condition()
        if completeness_condition:
            self.REVIEW_MANAGER.logger.info(
                " Completeness of iteration".ljust(32, " ") + "YES (validated)"
            )
        else:
            self.REVIEW_MANAGER.logger.error(
                "Completeness of iteration".ljust(32, " ") + "NO"
            )

        git_repo.git.checkout(cur_branch, force=True)

        return

    def main(
        self, scope: str, properties: bool = False, target_commit: str = None
    ) -> None:

        if properties:
            self.validate_properties(target_commit)
            return

        # extension: filter for changes of contributor (git author)
        records = self.load_records(target_commit)

        # Note: search records are considered immutable
        # we therefore load the latest files
        search_records = self.get_search_records()

        if "prepare" == scope or "all" == scope:
            self.validate_preparation_changes(records, search_records)

        if "merge" == scope or "all" == scope:
            self.validate_merging_changes(records, search_records)

        return


if __name__ == "__main__":
    pass
