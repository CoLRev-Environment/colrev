#! /usr/bin/env python
from __future__ import annotations

import csv
import typing
from pathlib import Path

import pandas as pd

import colrev.ops.built_in.pdf_get_man as built_in_pdf_get_man
import colrev.process
import colrev.record


class PDFGetMan(colrev.process.Process):

    built_in_scripts: dict[str, dict[str, typing.Any]] = {
        "colrev_cli_pdf_get_man": {
            "endpoint": built_in_pdf_get_man.CoLRevCLIPDFGetMan,
        }
    }

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.pdf_get_man,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.verbose = True

        package_manager = self.review_manager.get_package_manager()
        self.pdf_get_man_scripts: dict[str, typing.Any] = package_manager.load_packages(
            process=self,
            scripts=review_manager.settings.pdf_get.man_pdf_get_scripts,
        )

    def get_pdf_get_man(self, *, records: dict) -> list:
        missing_records = []
        for record in records.values():
            if (
                record["colrev_status"]
                == colrev.record.RecordState.pdf_needs_manual_retrieval
            ):
                missing_records.append(record)
        return missing_records

    def export_retrieval_table(self, *, records: dict) -> None:
        missing_records = self.get_pdf_get_man(records=records)
        missing_pdf_files_csv = Path("missing_pdf_files.csv")

        if len(missing_records) > 0:
            missing_records_df = pd.DataFrame.from_records(missing_records)
            # pylint: disable=duplicate-code
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

            self.review_manager.logger.info(
                "Created missing_pdf_files.csv with paper details"
            )

    def get_data(self) -> dict:

        self.review_manager.pdf_directory.mkdir(exist_ok=True)

        record_state_list = self.review_manager.dataset.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev.record.RecordState.pdf_needs_manual_retrieval)
                == x["colrev_status"]
            ]
        )
        pad = min((max(len(x["ID"]) for x in record_state_list) + 2), 40)
        items = self.review_manager.dataset.read_next_record(
            conditions=[
                {"colrev_status": colrev.record.RecordState.pdf_needs_manual_retrieval}
            ]
        )
        pdf_get_man_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(pdf_get_man_data)
        )
        return pdf_get_man_data

    def pdfs_retrieved_manually(self) -> bool:
        return self.review_manager.dataset.has_changes()

    def main(self) -> None:

        records = self.review_manager.dataset.load_records_dict()

        for (
            man_pdf_get_script
        ) in self.review_manager.settings.pdf_get.man_pdf_get_scripts:

            endpoint = self.pdf_get_man_scripts[man_pdf_get_script["endpoint"]]

            records = endpoint.get_man_pdf(self, records)


if __name__ == "__main__":
    pass
