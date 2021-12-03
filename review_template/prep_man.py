#! /usr/bin/env python
import logging
import os
import pprint

import bibtexparser
import pandas as pd
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from review_template import prepare
from review_template.review_manager import RecordState

logger = logging.getLogger("review_template")

pp = pprint.PrettyPrinter(indent=4, width=140)


def prep_man_stats(REVIEW_MANAGER) -> None:
    # TODO : this function mixes return values and saving to files.
    logger.info("Load references.bib")
    bib_db = REVIEW_MANAGER.load_main_refs()

    logger.info("Calculate statistics")
    stats = {"ENTRYTYPE": {}}
    overall_types = {"ENTRYTYPE": {}}
    prep_man_hints = []
    origins = []
    crosstab = []
    for record in bib_db.entries:
        if RecordState.md_imported != record["status"]:
            if record["ENTRYTYPE"] in overall_types["ENTRYTYPE"]:
                overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                    overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                )
            else:
                overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

        if RecordState.md_needs_manual_preparation != record["status"]:
            continue

        if record["ENTRYTYPE"] in stats["ENTRYTYPE"]:
            stats["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
            )
        else:
            stats["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

        if "man_prep_hints" in record:
            hints = record["man_prep_hints"].split(";")
            prep_man_hints.append(hints)
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
    logger.info("Writing data to file: manual_cleansing_statistics.csv")
    tabulated.to_csv("manual_cleansing_statistics.csv")

    # TODO : these should be combined in one dict and returned:
    print("Entry type statistics overall:")
    pp.pprint(overall_types["ENTRYTYPE"])

    print("Entry type statistics (needs_manual_cleansing):")
    pp.pprint(stats["ENTRYTYPE"])

    return


def extract_needs_prep_man(REVIEW_MANAGER) -> None:
    logger.info("Load references")
    bib_db = REVIEW_MANAGER.load_main_refs()

    bib_db.entries = [
        record
        for record in bib_db.entries
        if RecordState.md_needs_manual_preparation == record["status"]
    ]

    os.mkdir("prep_man")
    os.mkdir("prep_man/search")

    with open("prep_man/references_need_prep_man_export.bib", "w") as fi:
        fi.write(bibtexparser.dumps(bib_db))

    logger.info("Load origins")

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

        with open("prep_man/search/" + file, "w") as fi:
            fi.write(bibtexparser.dumps(search_db))

    return


def get_data(REVIEW_MANAGER):
    from review_template.review_manager import RecordState

    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [
            x
            for x in record_state_list
            if str(RecordState.md_needs_manual_preparation) == x[1]
        ]
    )

    all_ids = [x[0] for x in record_state_list]

    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)
    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": str(RecordState.md_needs_manual_preparation)}
    )
    return {"nr_tasks": nr_tasks, "PAD": PAD, "items": items, "all_ids": all_ids}


def update_record(REVIEW_MANAGER, record, PAD):
    from review_template.review_manager import RecordState

    record.update(status=RecordState.md_prepared)
    record.update(metadata_source="MAN_PREP")
    record = prepare.drop_fields(record)

    logger.info(f" {record['ID']}".ljust(PAD, " ") + "Excluded in screen")
    REVIEW_MANAGER.replace_record_by_ID(record)

    return
