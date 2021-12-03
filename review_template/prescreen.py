#! /usr/bin/env python
import csv
import logging
import os

import pandas as pd

from review_template.review_manager import RecordState

MAIN_REFERENCES = "NA"

logger = logging.getLogger("review_template")


def export_table(REVIEW_MANAGER, export_table_format: str) -> None:

    bib_db = REVIEW_MANAGER.load_main_refs()

    tbl = []
    for record in bib_db.entries:

        inclusion_1, inclusion_2 = "NA", "NA"

        if RecordState.md_retrieved == record["status"]:
            inclusion_1 = "TODO"
        if RecordState.rev_prescreen_excluded == record["status"]:
            inclusion_1 = "no"
        else:
            inclusion_1 = "yes"
            inclusion_2 = "TODO"
            if RecordState.rev_excluded == record["status"]:
                inclusion_2 = "no"
            if record["status"] in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                inclusion_2 = "yes"

        excl_criteria = {}
        if "excl_criteria" in record:
            for ecrit in record["excl_criteria"].split(";"):
                criteria = {ecrit.split("=")[0]: ecrit.split("=")[1]}
                excl_criteria.update(criteria)

        row = {
            "ID": record["ID"],
            "author": record.get("author", ""),
            "title": record.get("title", ""),
            "journal": record.get("journal", ""),
            "booktitle": record.get("booktitle", ""),
            "year": record.get("year", ""),
            "volume": record.get("volume", ""),
            "number": record.get("number", ""),
            "pages": record.get("pages", ""),
            "doi": record.get("doi", ""),
            "abstract": record.get("abstract", ""),
            "inclusion_1": inclusion_1,
            "inclusion_2": inclusion_2,
        }
        row.update(excl_criteria)
        tbl.append(row)

    if "csv" == export_table_format.lower():
        screen_df = pd.DataFrame(tbl)
        screen_df.to_csv("screen_table.csv", index=False, quoting=csv.QUOTE_ALL)
        logger.info("Created screen_table (csv)")

    if "xlsx" == export_table_format.lower():
        screen_df = pd.DataFrame(tbl)
        screen_df.to_excel("screen_table.xlsx", index=False, sheet_name="screen")
        logger.info("Created screen_table (xlsx)")

    return


def import_table(REVIEW_MANAGER, import_table_path: str) -> None:
    bib_db = REVIEW_MANAGER.load_main_refs()
    if not os.path.exists(import_table_path):
        logger.error(f"Did not find {import_table_path} - exiting.")
        return
    screen_df = pd.read_csv(import_table_path)
    screen_df.fillna("", inplace=True)
    records = screen_df.to_dict("records")

    logger.warning(
        "import_table not yet completed " "(exclusion_criteria are not yet imported)"
    )
    for x in [
        [x.get("ID", ""), x.get("inclusion_1", ""), x.get("inclusion_2", "")]
        for x in records
    ]:
        record = [e for e in bib_db.entries if e["ID"] == x[0]]
        if len(record) == 1:
            record = record[0]
            if x[1] == "no":
                record["status"] = RecordState.rev_prescreen_excluded
            if x[1] == "yes":
                record["status"] = RecordState.rev_prescreen_included
            if x[2] == "no":
                record["status"] = RecordState.rev_excluded
            if x[2] == "yes":
                record["status"] = RecordState.rev_included
            # TODO: exclusion-criteria

    REVIEW_MANAGER.save_bib_file(bib_db)

    return


def include_all_in_prescreen(REVIEW_MANAGER) -> None:

    bib_db = REVIEW_MANAGER.load_main_refs()

    saved_args = locals()
    PAD = 50  # TODO
    for record in bib_db.entries:
        if record["status"] in [RecordState.md_retrieved, RecordState.md_processed]:
            continue
        logger.info(
            f' {record["ID"]}'.ljust(PAD, " ") + "Included in prescreen (automatically)"
        )
        record.update(status=RecordState.rev_prescreen_included)

    REVIEW_MANAGER.save_bib_file(bib_db)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([MAIN_REFERENCES])
    REVIEW_MANAGER.create_commit(
        "Pre-screening (manual)", saved_args, manual_author=False
    )

    return


def get_data(REVIEW_MANAGER):
    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [x for x in record_state_list if str(RecordState.md_processed) == x[1]]
    )
    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 40)
    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": str(RecordState.md_processed)}
    )
    return {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}


def set_prescreen_status(REVIEW_MANAGER, ID, PAD, prescreen_inclusion: bool) -> None:

    git_repo = REVIEW_MANAGER.get_repo()
    if prescreen_inclusion:
        logger.info(f" {ID}".ljust(PAD, " ") + "Included in prescreen")
        REVIEW_MANAGER.replace_field(
            ID, "status", str(RecordState.rev_prescreen_included)
        )
        git_repo.index.add([REVIEW_MANAGER.paths["MAIN_REFERENCES"]])
    else:
        logger.info(f" {ID}".ljust(PAD, " ") + "Excluded in prescreen")
        REVIEW_MANAGER.replace_field(
            ID, "status", str(RecordState.rev_prescreen_excluded)
        )
        git_repo.index.add([REVIEW_MANAGER.paths["MAIN_REFERENCES"]])

    return
