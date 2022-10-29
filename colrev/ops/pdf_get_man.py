#! /usr/bin/env python
"""CoLRev pdf_get_man operation: Get PDF documents manually."""
from __future__ import annotations

import csv
import typing
from pathlib import Path

import pandas as pd

import colrev.operation
import colrev.record


class PDFGetMan(colrev.operation.Operation):
    """Get PDFs manually"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.pdf_get_man,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.verbose = True

        package_manager = self.review_manager.get_package_manager()
        self.pdf_get_man_package_endpoints: dict[
            str, typing.Any
        ] = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.pdf_get_man,
            selected_packages=review_manager.settings.pdf_get.pdf_get_man_package_endpoints,
            operation=self,
        )

    def get_pdf_get_man(self, *, records: dict) -> list:
        """Get the records that are missing a PDF"""
        missing_records = []
        for record in records.values():
            if (
                record["colrev_status"]
                == colrev.record.RecordState.pdf_needs_manual_retrieval
            ):
                missing_records.append(record)
        return missing_records

    def export_retrieval_table(self, *, records: dict) -> None:
        """Export a table for manual PDF retrieval"""

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

    def discard(self) -> None:
        """Discard missing PDFs (set to pdf_not_available)"""

        records = self.review_manager.dataset.load_records_dict()
        for record in records.values():
            if (
                record["colrev_status"]
                == colrev.record.RecordState.pdf_needs_manual_retrieval
            ):
                record["colrev_status"] = colrev.record.RecordState.pdf_not_available
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg="Discard missing PDFs", manual_author=True
        )

    def get_data(self) -> dict:
        """Get the data for pdf-get-man"""
        # pylint: disable=duplicate-code

        self.review_manager.pdf_dir.mkdir(exist_ok=True)

        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        nr_tasks = len(
            [
                x
                for x in record_header_list
                if colrev.record.RecordState.pdf_needs_manual_retrieval
                == x["colrev_status"]
            ]
        )
        pad = min((max(len(x["ID"]) for x in record_header_list) + 2), 40)
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
        """Check whether PDFs were retrieved manually"""
        return self.review_manager.dataset.has_changes()

    def main(self) -> None:
        """Get PDFs manually (main entrypoint)"""

        records = self.review_manager.dataset.load_records_dict()

        for (
            pdf_get_man_package_endpoint
        ) in self.review_manager.settings.pdf_get.pdf_get_man_package_endpoints:

            endpoint = self.pdf_get_man_package_endpoints[
                pdf_get_man_package_endpoint["endpoint"]
            ]

            records = endpoint.pdf_get_man(self, records)


if __name__ == "__main__":
    pass
