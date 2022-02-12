#! /usr/bin/env python
import csv
import typing
from pathlib import Path

import pandas as pd

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class PDFRetrievalMan(Process):
    def __init__(self):

        super().__init__(ProcessType.pdf_get_man)

        self.REVIEW_MANAGER.notify(self)

    def get_pdf_get_man(self, records: typing.List[dict]) -> list:
        missing_records = []
        for record in records:
            if record["status"] == RecordState.pdf_needs_manual_retrieval:
                missing_records.append(record)
        return missing_records

    def export_retrieval_table(self, records: typing.List[dict]) -> None:
        missing_records = self.get_pdf_get_man(records)
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

            self.logger.info("Created missing_pdf_files.csv with paper details")
        return

    def get_data(self) -> dict:

        self.REVIEW_MANAGER.paths["PDF_DIRECTORY"].mkdir(exist_ok=True)

        self.REVIEW_MANAGER.notify(Process(ProcessType.pdf_get_man))
        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.pdf_needs_manual_retrieval) == x[1]
            ]
        )
        PAD = min((max(len(x[0]) for x in record_state_list) + 2), 40)
        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions={"status": RecordState.pdf_needs_manual_retrieval}
        )
        pdf_get_man_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.logger.debug(self.pp.pformat(pdf_get_man_data))
        return pdf_get_man_data

    def set_data(self, record, filepath: Path, PAD: int = 40) -> None:

        if filepath is None:
            record.update(status=RecordState.pdf_not_available)
            self.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "recorded as not_available"
            )
            self.logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "recorded as not_available"
            )

        else:
            record.update(status=RecordState.pdf_imported)
            record.update(file=str(filepath))
            self.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "retrieved and linked PDF"
            )
            self.logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "retrieved and linked PDF"
            )

        self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(record)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def pdfs_retrieved_manually(self) -> bool:
        git_repo = self.REVIEW_MANAGER.get_repo()
        return git_repo.is_dirty()


if __name__ == "__main__":
    pass
