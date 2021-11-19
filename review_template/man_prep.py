#! /usr/bin/env python
import logging
import os
import pprint

import bibtexparser
import git
import pandas as pd
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from review_template import prepare
from review_template import repo_setup
from review_template import utils


record_type_mapping = {
    "a": "article",
    "p": "inproceedings",
    "b": "book",
    "ib": "inbook",
    "pt": "phdthesis",
    "mt": "masterthesis",
    "o": "other",
    "unp": "unpublished",
}

ID_list = []

pp = pprint.PrettyPrinter(indent=4, width=140)


def print_record(record: dict) -> None:
    # Escape sequence to clear terminal output for each new comparison
    os.system("cls" if os.name == "nt" else "clear")
    pp.pprint(record)
    if "title" in record:
        print(
            "https://scholar.google.de/scholar?hl=de&as_sdt=0%2C5&q="
            + record["title"].replace(" ", "+")
        )
    return


def man_correct_recordtype(record: dict) -> dict:

    if "n" == input("ENTRYTYPE=" + record["ENTRYTYPE"] + " correct?"):
        choice = input(
            "Correct type: "
            + "a (article), p (inproceedings), "
            + "b (book), ib (inbook), "
            + "pt (phdthesis), mt (masterthesis), "
            "unp (unpublished), o (other), "
        )
        assert choice in record_type_mapping.keys()
        correct_record_type = [
            value for (key, value) in record_type_mapping.items() if key == choice
        ]
        record["ENTRYTYPE"] = correct_record_type[0]
    return record


def man_provide_required_fields(record: dict) -> dict:
    if prepare.is_complete(record):
        return record

    reqs = prepare.record_field_requirements[record["ENTRYTYPE"]]
    for field in reqs:
        if field not in record:
            value = input("Please provide the " + field + " (or NA)")
            record[field] = value
    return record


def man_fix_field_inconsistencies(record: dict) -> dict:
    if not prepare.has_inconsistent_fields(record):
        return record

    print("TODO: ask whether the inconsistent fields can be dropped?")

    return record


def man_fix_incomplete_fields(record: dict) -> dict:
    if not prepare.has_incomplete_fields(record):
        return record

    print("TODO: ask for completion of fields")
    # organize has_incomplete_fields() values in a dict?

    return record


def man_prep_records() -> None:
    saved_args = locals()
    global ID_list

    repo = git.Repo("")
    utils.require_clean_repo(repo)

    print("TODO: include processing_reports")

    logging.info("Loading records for manual preparation...")
    bib_db = utils.load_main_refs()

    ID_list = [record["ID"] for record in bib_db.entries]

    i = 1
    stat_len = len(
        [
            x
            for x in bib_db.entries
            if "needs_manual_preparation" == x.get("rev_status", "NA")
        ]
    )
    if 0 == stat_len:
        logging.info("No records to prepare manually")
        return

    for record in bib_db.entries:

        if "needs_manual_preparation" != record["md_status"]:
            continue

        os.system("cls" if os.name == "nt" else "clear")
        print(f"{i}/{stat_len}")
        i += 1

        print_record(record)

        man_correct_recordtype(record)
        man_provide_required_fields(record)
        man_fix_field_inconsistencies(record)
        man_fix_incomplete_fields(record)

        # Note: for complete_based_on_doi field:
        record = prepare.retrieve_doi_metadata(record)

        if (
            (prepare.is_complete(record) or prepare.is_doi_complete(record))
            and not prepare.has_inconsistent_fields(record)
            and not prepare.has_incomplete_fields(record)
        ):
            record = prepare.drop_fields(record)
            record.update(
                ID=utils.generate_ID_blacklist(
                    record, ID_list, record_in_bib_db=True, raise_error=False
                )
            )
            ID_list.append(record["ID"])
            record.update(md_status="prepared")
            record.update(metadata_source="MAN_PREP")

        utils.save_bib_file(bib_db)

    bib_db = utils.set_IDs(bib_db)
    MAIN_REFERENCES = repo_setup.paths["MAIN_REFERENCES"]
    utils.save_bib_file(bib_db, MAIN_REFERENCES)
    repo.index.add([MAIN_REFERENCES])

    utils.create_commit(
        repo, "Prepare records for import", saved_args, manual_author=True
    )
    return


def man_prep_stats() -> None:
    logging.info("Load references.bib")
    bib_db = utils.load_main_refs()

    logging.info("Calculate statistics")
    stats = {"ENTRYTYPE": {}}
    overall_types = {"ENTRYTYPE": {}}
    man_prep_hints = []
    origins = []
    crosstab = []
    for record in bib_db.entries:
        if "imported" != record.get("md_status", "NA"):
            if record["ENTRYTYPE"] in overall_types["ENTRYTYPE"]:
                overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                    overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                )
            else:
                overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

        if "needs_manual_preparation" != record.get("md_status", "NA"):
            continue

        if record["ENTRYTYPE"] in stats["ENTRYTYPE"]:
            stats["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
            )
        else:
            stats["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

        if "man_prep_hints" in record:
            hints = record["man_prep_hints"].split(";")
            man_prep_hints.append(hints)
            for hint in hints:
                if "change-score" in hint:
                    continue
                # Note: if something causes the needs_manual_preparation
                # it is caused by all origins
                for orig in record.get("origin", "NA").split(";"):
                    crosstab.append([orig[: orig.rfind("/")], hint])

        origins.append(
            [x[: x.rfind("/")] for x in record.get("origin", "NA").split(";")]
        )

    print("Entry type statistics overall:")
    pp.pprint(overall_types["ENTRYTYPE"])

    print("Entry type statistics (needs_manual_cleansing):")
    pp.pprint(stats["ENTRYTYPE"])

    crosstab_df = pd.DataFrame(crosstab, columns=["origin", "hint"])

    tabulated = pd.pivot_table(
        crosstab_df[["origin", "hint"]],
        index=["origin"],
        columns=["hint"],
        aggfunc=len,
        fill_value=0,
        margins=True,
    )
    # .sort_index(axis='columns')
    tabulated.sort_values(by=["All"], ascending=False, inplace=True)
    print(tabulated)
    logging.info("Writing data to file: manual_cleansing_statistics.csv")
    tabulated.to_csv("manual_cleansing_statistics.csv")
    return


def extract_needs_man_prep() -> None:
    logging.info("Load references")
    bib_db = utils.load_main_refs(mod_check=False)

    bib_db.entries = bib_db.entries[1:1000]
    print(len(bib_db.entries))

    bib_db.entries = [
        r
        for r in bib_db.entries
        if "needs_manual_preparation" == r.get("md_status", "NA")
    ]

    os.mkdir("man_prep")
    os.mkdir("man_prep/search")

    with open("man_prep/references_need_man_prep_export.bib", "w") as fi:
        fi.write(bibtexparser.dumps(bib_db))

    logging.info("Load origins")

    origin_list = []
    for record in bib_db.entries:
        for orig in record.get("origin", "NA").split(";"):
            origin_list.append(orig.split("/"))

    search_results_list = {}
    for file, id in origin_list:
        if file in search_results_list:
            search_results_list[file].append(id)
        else:
            search_results_list[file] = [id]

    for file, id_list in search_results_list.items():
        search_db = BibDatabase()
        print(file)
        with open("search/" + file) as sr_db_path:
            sr_db = BibTexParser(
                customization=convert_to_unicode,
                ignore_nonstandard_types=False,
                common_strings=True,
            ).parse_file(sr_db_path, partial=True)
        for id in id_list:
            orig_rec = [r for r in sr_db.entries if id == r["ID"]][0]
            search_db.entries.append(orig_rec)
        print(len(search_db.entries))

        with open("man_prep/search/" + file, "w") as fi:
            fi.write(bibtexparser.dumps(search_db))

    return


def main(stats: bool = False, extract: bool = False) -> None:

    if stats:
        man_prep_stats()
    elif extract:
        extract_needs_man_prep()
    else:
        man_prep_records()
    return
