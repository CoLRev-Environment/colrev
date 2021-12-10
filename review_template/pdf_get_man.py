#! /usr/bin/env python
import csv
import logging

import pandas as pd
from bibtexparser.bibdatabase import BibDatabase

from review_template.review_manager import RecordState

report_logger = logging.getLogger("review_template_report")
logger = logging.getLogger("review_template")


# https://github.com/ContentMine/getpapers

existing_pdfs_linked = 0


def get_pdf_get_man(bib_db: BibDatabase) -> list:
    missing_records = []
    for record in bib_db.entries:
        if record["status"] == RecordState.pdf_needs_manual_retrieval:
            missing_records.append(record)
    return missing_records


def export_retrieval_table(bib_db: BibDatabase) -> None:
    missing_records = get_pdf_get_man(bib_db)

    if len(missing_records) > 0:
        missing_records_df = pd.DataFrame.from_records(missing_records)
        col_order = [
            "ID",
            "author",
            "title",
            "journal",
            "booktitle",
            "year",
            "volume",
            "number",
            "pages",
            "doi",
        ]
        missing_records_df = missing_records_df.reindex(col_order, axis=1)
        missing_records_df.to_csv(
            "missing_pdf_files.csv", index=False, quoting=csv.QUOTE_ALL
        )

        logger.info("Created missing_pdf_files.csv with paper details")
    return


def get_data(REVIEW_MANAGER):
    from review_template.review_manager import Process, ProcessType

    REVIEW_MANAGER.paths["PDF_DIRECTORY"].mkdir(parents=True, exist_ok=True)

    REVIEW_MANAGER.notify(Process(ProcessType.pdf_get_man))
    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [
            x
            for x in record_state_list
            if str(RecordState.pdf_needs_manual_retrieval) == x[1]
        ]
    )
    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 40)
    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": str(RecordState.pdf_needs_manual_retrieval)}
    )
    return {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}


def pdfs_retrieved_maually(REVIEW_MANAGER) -> bool:
    git_repo = REVIEW_MANAGER.get_repo()
    return git_repo.is_dirty()


def set_data(REVIEW_MANAGER, record, filepath: str, PAD: int = 40) -> None:

    git_repo = REVIEW_MANAGER.get_repo()

    if filepath is None:
        record.update(status=RecordState.pdf_not_available)
        report_logger.info(
            f" {record['ID']}".ljust(PAD, " ") + "recorded as not_available"
        )
        logger.info(f" {record['ID']}".ljust(PAD, " ") + "recorded as not_available")

    else:
        record.update(status=RecordState.pdf_imported)
        record.update(file=filepath)
        if "GIT" == REVIEW_MANAGER.config["PDF_HANDLING"]:
            git_repo.index.add([filepath])
        report_logger.info(
            f" {record['ID']}".ljust(PAD, " ") + "retrieved and linked PDF"
        )
        logger.info(f" {record['ID']}".ljust(PAD, " ") + "retrieved and linked PDF")

    REVIEW_MANAGER.update_record_by_ID(record)
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

    return
