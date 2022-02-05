#! /usr/bin/env python
import csv
import logging
import pprint
import typing
from pathlib import Path

import pandas as pd

from colrev_core.review_manager import RecordState

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")
pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


# https://github.com/ContentMine/getpapers


def get_pdf_get_man(records: typing.List[dict]) -> list:
    missing_records = []
    for record in records:
        if record["status"] == RecordState.pdf_needs_manual_retrieval:
            missing_records.append(record)
    return missing_records


def export_retrieval_table(records: typing.List[dict]) -> None:
    missing_records = get_pdf_get_man(records)
    missing_pdf_files_csv = Path("missing_pdf_files.csv")

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
            missing_pdf_files_csv, index=False, quoting=csv.QUOTE_ALL
        )

        logger.info("Created missing_pdf_files.csv with paper details")
    return


def get_data(REVIEW_MANAGER) -> dict:
    from colrev_core.review_manager import Process, ProcessType

    REVIEW_MANAGER.paths["PDF_DIRECTORY"].mkdir(exist_ok=True)

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
        conditions={"status": RecordState.pdf_needs_manual_retrieval}
    )
    pdf_get_man_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
    logger.debug(pp.pformat(pdf_get_man_data))
    return pdf_get_man_data


def set_data(REVIEW_MANAGER, record, filepath: Path, PAD: int = 40) -> None:

    if filepath is None:
        record.update(status=RecordState.pdf_not_available)
        report_logger.info(
            f" {record['ID']}".ljust(PAD, " ") + "recorded as not_available"
        )
        logger.info(f" {record['ID']}".ljust(PAD, " ") + "recorded as not_available")

    else:
        record.update(status=RecordState.pdf_imported)
        record.update(file=str(filepath))
        report_logger.info(
            f" {record['ID']}".ljust(PAD, " ") + "retrieved and linked PDF"
        )
        logger.info(f" {record['ID']}".ljust(PAD, " ") + "retrieved and linked PDF")

    REVIEW_MANAGER.update_record_by_ID(record)
    REVIEW_MANAGER.add_record_changes()

    return


def pdfs_retrieved_manually(REVIEW_MANAGER) -> bool:
    git_repo = REVIEW_MANAGER.get_repo()
    return git_repo.is_dirty()
