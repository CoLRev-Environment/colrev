#! /usr/bin/env python
import itertools
import logging
import multiprocessing as mp
import os
import pprint
from itertools import chain

import bibtexparser
import dictdiffer
import git
import pipeline_validation_hooks
from bashplotlib.histogram import plot_hist
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode
from pipeline_validation_hooks import check  # noqa: F401

from review_template import dedupe
from review_template import status

CPUS = -1


def load_records(bib_file: str) -> list:

    with open(bib_file) as bibtex_file:
        individual_bib_db = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode,
            common_strings=True,
        ).parse_file(bibtex_file, partial=True)
        search_file = os.path.basename(bib_file)
        for record in individual_bib_db.entries:
            record["origin"] = search_file + "/" + record["ID"]

    return individual_bib_db.entries


def get_search_records(REVIEW_MANAGER) -> list:

    pool = mp.Pool(CPUS)
    records = pool.map(load_records, REVIEW_MANAGER.get_bib_files())
    records = list(chain(*records))

    return records


def validate_preparation_changes(bib_db: BibDatabase, search_records: list) -> None:

    logging.info("Calculating preparation differences...")
    change_diff = []
    for record in bib_db.entries:
        if "changed_in_target_commit" not in record:
            continue
        del record["changed_in_target_commit"]
        del record["rev_status"]
        del record["md_status"]
        del record["pdf_status"]
        # del record['origin']
        for cur_record_link in record["origin"].split(";"):
            prior_records = [
                x for x in search_records if cur_record_link in x["origin"].split(",")
            ]
            for prior_record in prior_records:
                similarity = dedupe.get_record_similarity(record, prior_record)
                change_diff.append([record["ID"], cur_record_link, similarity])

    change_diff = [[e1, e2, 1 - sim] for [e1, e2, sim] in change_diff if sim < 1]
    # sort according to similarity
    change_diff.sort(key=lambda x: x[2], reverse=True)

    if 0 == len(change_diff):
        logging.info("No substantial differences found.")

    plot_hist(
        [sim for [e1, e2, sim] in change_diff],
        bincount=100,
        xlab=True,
        showSummary=True,
    )
    input("continue")

    pp = pprint.PrettyPrinter(indent=4)
    for eid, record_link, difference in change_diff:
        # Escape sequence to clear terminal output for each new comparison
        os.system("cls" if os.name == "nt" else "clear")
        logging.info("Record with ID: " + eid)

        logging.info("Difference: " + str(round(difference, 4)) + "\n\n")
        record_1 = [x for x in search_records if record_link == x["origin"]]
        pp.pprint(record_1[0])
        record_2 = [x for x in bib_db.entries if eid == x["ID"]]
        pp.pprint(record_2[0])

        print("\n\n")
        for diff in list(dictdiffer.diff(record_1, record_2)):
            # Note: may treat fields differently (e.g., status, ID, ...)
            pp.pprint(diff)

        if "n" == input("continue (y/n)?"):
            break
        # input('TODO: correct? if not, replace current record with old one')

    return


def validate_merging_changes(bib_db: BibDatabase, search_records: list) -> None:

    os.system("cls" if os.name == "nt" else "clear")
    logging.info("Calculating differences between merged records...")
    change_diff = []
    merged_records = False
    for record in bib_db.entries:
        if "changed_in_target_commit" not in record:
            continue
        del record["changed_in_target_commit"]
        if ";" in record["origin"]:
            merged_records = True
            els = record["origin"].split(";")
            duplicate_el_pairs = list(itertools.combinations(els, 2))
            for el_1, el_2 in duplicate_el_pairs:
                record_1 = [x for x in search_records if el_1 == x["origin"]]
                record_2 = [x for x in search_records if el_2 == x["origin"]]

                similarity = dedupe.get_record_similarity(record_1[0], record_2[0])
                change_diff.append([el_1, el_2, similarity])

    change_diff = [[e1, e2, 1 - sim] for [e1, e2, sim] in change_diff if sim < 1]

    # sort according to similarity
    change_diff.sort(key=lambda x: x[2], reverse=True)

    if 0 == len(change_diff):
        if merged_records:
            logging.info("No substantial differences found.")
        else:
            logging.info("No merged records")

    pp = pprint.PrettyPrinter(indent=4)

    for el_1, el_2, difference in change_diff:
        # Escape sequence to clear terminal output for each new comparison
        os.system("cls" if os.name == "nt" else "clear")

        print("Differences between merged records:" + f" {round(difference, 4)}\n\n")
        record_1 = [x for x in search_records if el_1 == x["origin"]]
        pp.pprint(record_1[0])
        record_2 = [x for x in search_records if el_2 == x["origin"]]
        pp.pprint(record_2[0])

        if "n" == input("continue (y/n)?"):
            break
        # TODO: explain users how to change it/offer option to reverse!

    return


def load_bib_db(REVIEW_MANAGER, target_commit: str) -> BibDatabase:

    if "none" == target_commit:
        logging.info("Loading data...")
        bib_db = REVIEW_MANAGER.load_main_refs()
        [x.update(changed_in_target_commit="True") for x in bib_db.entries]

    else:
        logging.info("Loading data from history...")
        repo = git.Repo()

        MAIN_REFERENCES = REVIEW_MANAGER.paths["MAIN_REFERENCES"]

        revlist = (
            (commit.hexsha, (commit.tree / MAIN_REFERENCES).data_stream.read())
            for commit in repo.iter_commits(paths=MAIN_REFERENCES)
        )
        found = False
        for commit, filecontents in list(revlist):
            if found:  # load the MAIN_REFERENCES in the following commit
                prior_bib_db = bibtexparser.loads(filecontents)
                break
            if commit == target_commit:
                bib_db = bibtexparser.loads(filecontents)
                found = True

        # determine which records have been changed (prepared or merged)
        # in the target_commit
        for record in bib_db.entries:
            prior_record = [x for x in prior_bib_db.entries if x["ID"] == record["ID"]][
                0
            ]
            # Note: the following is an exact comparison of all fields
            if record != prior_record:
                record.update(changed_in_target_commit="True")

    return bib_db


def validate_properties(target_commit: str) -> None:
    # TODO: option: --history: check all preceding commits (create a list...)
    repo = git.Repo()
    cur_sha = repo.head.commit.hexsha
    cur_branch = repo.active_branch.name
    logging.info(f"Current commit: {cur_sha} (branch {cur_branch})")

    if not target_commit:
        target_commit = cur_sha
    if repo.is_dirty() and not target_commit == cur_sha:
        logging.error(
            "Error: Need a clean repository to validate properties " "of prior commit"
        )
        return
    if not target_commit == cur_sha:
        logging.info(f"Check out target_commit = {target_commit}")
        repo.git.checkout(target_commit)

    completeness_condition = status.get_completeness_condition()
    if completeness_condition:
        logging.info("Completeness of iteration".ljust(32, " ") + "YES (validated)")
    else:
        logging.error("Completeness of iteration".ljust(32, " ") + "NO")
    if 0 == pipeline_validation_hooks.check.main():
        logging.info("Traceability of records".ljust(32, " ") + "YES (validated)")
        logging.info("Consistency (based on hooks)".ljust(32, " ") + "YES (validated)")
    else:
        logging.error("Traceability of records".ljust(32, " ") + "NO")
        logging.error("Consistency (based on hooks)".ljust(32, " ") + "NO")

    repo.git.checkout(cur_branch, force=True)

    return


def main(
    REVIEW_MANAGER, scope: str, properties: bool = False, target_commit: str = None
) -> None:

    global CPUS
    CPUS = REVIEW_MANAGER.config["CPUS"]

    if properties:
        validate_properties(target_commit)
        return

    # TODO: extension: filter for changes of contributor (git author)
    bib_db = load_bib_db(REVIEW_MANAGER, target_commit)

    # Note: search records are considered immutable
    # we therefore load the latest files
    search_records = get_search_records(REVIEW_MANAGER)

    if "prepare" == scope or "all" == scope:
        validate_preparation_changes(bib_db, search_records)

    if "merge" == scope or "all" == scope:
        validate_merging_changes(bib_db, search_records)

    return
