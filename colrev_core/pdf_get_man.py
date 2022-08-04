#! /usr/bin/env python
import csv
import typing
from pathlib import Path

import pandas as pd

from colrev_core.built_in import pdf_get_man as built_in_pdf_get_man
from colrev_core.environment import AdapterManager
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class PDFRetrievalMan(Process):

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "colrev_cli_pdf_get_man": {
            "endpoint": built_in_pdf_get_man.CoLRevCLIPDFRetrievalManual,
        }
    }

    def __init__(self, *, REVIEW_MANAGER, notify_state_transition_process: bool = True):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=ProcessType.pdf_get_man,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True
        self.pdf_get_man_scripts: typing.Dict[
            str, typing.Any
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=REVIEW_MANAGER.settings.pdf_get.man_pdf_get_scripts,
        )

    def get_pdf_get_man(self, *, records: typing.Dict) -> list:
        missing_records = []
        for record in records.values():
            if record["colrev_status"] == RecordState.pdf_needs_manual_retrieval:
                missing_records.append(record)
        return missing_records

    def export_retrieval_table(self, *, records: typing.Dict) -> None:
        missing_records = self.get_pdf_get_man(records=records)
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

            self.REVIEW_MANAGER.logger.info(
                "Created missing_pdf_files.csv with paper details"
            )

    def get_data(self) -> dict:

        self.REVIEW_MANAGER.paths["PDF_DIRECTORY"].mkdir(exist_ok=True)

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.pdf_needs_manual_retrieval) == x["colrev_status"]
            ]
        )
        PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 40)
        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"colrev_status": RecordState.pdf_needs_manual_retrieval}]
        )
        pdf_get_man_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.REVIEW_MANAGER.logger.debug(
            self.REVIEW_MANAGER.pp.pformat(pdf_get_man_data)
        )
        return pdf_get_man_data

    def pdfs_retrieved_manually(self) -> bool:
        return self.REVIEW_MANAGER.REVIEW_DATASET.has_changes()

    def main(self) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for (
            PDF_GET_MAN_SCRIPT
        ) in self.REVIEW_MANAGER.settings.pdf_get.man_pdf_get_scripts:

            ENDPOINT = self.pdf_get_man_scripts[PDF_GET_MAN_SCRIPT["endpoint"]]

            records = ENDPOINT.get_man_pdf(self, records)


if __name__ == "__main__":
    pass
