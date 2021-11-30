#! /usr/bin/env python
import csv
import logging
import os

import bibtexparser
import pandas as pd
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

MAIN_REFERENCES = "NA"


def export_table(REVIEW_MANAGER, export_table_format: str) -> None:

    bib_db = REVIEW_MANAGER.load_main_refs()

    tbl = []
    for record in bib_db.entries:

        inclusion_1, inclusion_2 = "NA", "NA"

        if "retrieved" == record["rev_status"]:
            inclusion_1 = "TODO"
        if "prescreen_excluded" == record["rev_status"]:
            inclusion_1 = "no"
        else:
            inclusion_1 = "yes"
            inclusion_2 = "TODO"
            if "excluded" == record["rev_status"]:
                inclusion_2 = "no"
            if record["rev_status"] in ["included", "synthesized"]:
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
        logging.info("Created screen_table (csv)")

    if "xlsx" == export_table_format.lower():
        screen_df = pd.DataFrame(tbl)
        screen_df.to_excel("screen_table.xlsx", index=False, sheet_name="screen")
        logging.info("Created screen_table (xlsx)")

    return


def import_table(REVIEW_MANAGER, import_table_path: str) -> None:
    bib_db = REVIEW_MANAGER.load_main_refs()
    if not os.path.exists(import_table_path):
        logging.error(f"Did not find {import_table_path} - exiting.")
        return
    screen_df = pd.read_csv(import_table_path)
    screen_df.fillna("", inplace=True)
    records = screen_df.to_dict("records")

    logging.warning(
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
                record["rev_status"] = "prescreen_excluded"
            if x[1] == "yes":
                record["rev_status"] = "prescreen_inclued"
            if x[2] == "no":
                record["rev_status"] = "excluded"
            if x[2] == "yes":
                record["rev_status"] = "included"
            # TODO: exclusion-criteria

    REVIEW_MANAGER.save_bib_file(bib_db)

    return


def include_all_in_prescreen(REVIEW_MANAGER) -> None:

    bib_db = REVIEW_MANAGER.load_main_refs()

    saved_args = locals()
    PAD = 50  # TODO
    for record in bib_db.entries:
        if record.get("rev_status", "NA") in ["retrieved", "processed"]:
            continue
        logging.info(
            f' {record["ID"]}'.ljust(PAD, " ") + "Included in prescreen (automatically)"
        )
        record.update(rev_status="prescreen_included")
        record.update(pdf_status="needs_retrieval")

    REVIEW_MANAGER.save_bib_file(bib_db)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([MAIN_REFERENCES])
    REVIEW_MANAGER.create_commit(
        "Pre-screening (manual)", saved_args, manual_author=False
    )

    return


def get_next_prescreening_item(REVIEW_MANAGER):
    prescreening_items = []
    for record_string in REVIEW_MANAGER.read_next_record_str():
        rev_stat = "NA"
        for line in record_string.split("\n"):
            if "rev_status" == line.lstrip()[:10]:
                rev_stat = line[line.find("{") + 1 : line.rfind("}")]
                if "retrieved" == rev_stat:
                    parser = BibTexParser(customization=convert_to_unicode)
                    db = bibtexparser.loads(record_string, parser=parser)
                    record = db.entries[0]
                    prescreening_items.append(record)
    yield from prescreening_items


def replace_field(REVIEW_MANAGER, ID, key: str, val: str) -> None:

    val = val.encode("utf-8")
    current_ID = "NA"
    with open(REVIEW_MANAGER.paths["MAIN_REFERENCES"], "r+b") as fd:
        seekpos = fd.tell()
        line = fd.readline()
        while line:
            if b"@" in line[:3]:
                current_ID = line[line.find(b"{") + 1 : line.rfind(b",")]
                current_ID = current_ID.decode("utf-8")

            replacement = None
            if current_ID == ID:
                if line.lstrip()[: len(key)].decode("utf-8") == key:
                    replacement = line[: line.find(b"{") + 1] + val + b"},\n"

            if replacement == ":q":
                break
            if replacement:
                if len(replacement) == len(line):
                    fd.seek(seekpos)
                    fd.write(replacement)
                    fd.flush()
                    os.fsync(fd)
                else:
                    remaining = fd.read()
                    fd.seek(seekpos)
                    fd.write(replacement)
                    seekpos = fd.tell()
                    fd.flush()
                    os.fsync(fd)
                    fd.write(remaining)
                    fd.truncate()  # if the replacement is shorter...
                    fd.seek(seekpos)
                    line = fd.readline()
                return  # We only need to replace once
            seekpos = fd.tell()
            line = fd.readline()
    return


def set_prescreen_status(REVIEW_MANAGER, ID, prescreen_inclusion: bool) -> None:

    if prescreen_inclusion:
        replace_field(REVIEW_MANAGER, ID, "rev_status", "prescreen_included")
        # TODO : the pdf_needs_retrieval must be added, not replaced
        replace_field(REVIEW_MANAGER, "pdf_status", "needs_retrieval")
    else:
        replace_field(REVIEW_MANAGER, ID, "rev_status", "prescreen_excluded")

    return
