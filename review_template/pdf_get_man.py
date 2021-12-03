#! /usr/bin/env python
import csv
import logging

import pandas as pd
from bibtexparser.bibdatabase import BibDatabase

from review_template.review_manager import RecordState

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
