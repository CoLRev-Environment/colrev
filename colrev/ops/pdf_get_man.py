#! /usr/bin/env python
"""CoLRev pdf_get_man operation: Get PDF documents manually."""
from __future__ import annotations

import csv
import typing
from pathlib import Path
from typing import Optional

import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record


class PDFGetMan(colrev.operation.Operation):
    """Get PDFs manually"""

    pdf_get_man_package_endpoints: dict[str, typing.Any]
    MISSING_PDF_FILES_RELATIVE = Path("data/pdf_get_man/missing_pdf_files.csv")

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

        self.missing_pdf_files_csv = (
            self.review_manager.path / self.MISSING_PDF_FILES_RELATIVE
        )
        self.verbose = True

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
            self.missing_pdf_files_csv.parent.mkdir(exist_ok=True, parents=True)
            missing_records_df.to_csv(
                self.missing_pdf_files_csv, index=False, quoting=csv.QUOTE_ALL
            )

            self.review_manager.logger.info(
                f"Created {self.missing_pdf_files_csv} with paper details"
            )

    def discard(self) -> None:
        """Discard missing PDFs (set to pdf_not_available)"""

        records = self.review_manager.dataset.load_records_dict()
        for record_dict in records.values():
            record = colrev.record.Record(data=record_dict)
            if (
                record.data["colrev_status"]
                == colrev.record.RecordState.pdf_needs_manual_retrieval
            ):
                record.set_status(
                    target_state=colrev.record.RecordState.pdf_not_available
                )
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

    def pdf_get_man_record(
        self,
        *,
        record: colrev.record.Record,
        filepath: Optional[Path] = None,
        PAD: int = 40,
    ) -> None:
        """Record pdf-get-man decision"""
        if filepath is not None:
            record.set_status(target_state=colrev.record.RecordState.pdf_imported)
            record.data.update(file=str(filepath.relative_to(self.review_manager.path)))
            self.review_manager.report_logger.info(
                f" {record.data['ID']}".ljust(PAD, " ") + "retrieved and linked PDF"
            )
            self.review_manager.logger.info(
                f" {record.data['ID']}".ljust(PAD, " ") + "retrieved and linked PDF"
            )
        else:
            if (
                self.review_manager.settings.pdf_get.pdf_required_for_screen_and_synthesis
            ):
                record.set_status(
                    target_state=colrev.record.RecordState.pdf_not_available
                )
                self.review_manager.report_logger.info(
                    f" {record.data['ID']}".ljust(PAD, " ")
                    + "recorded as not_available"
                )
                self.review_manager.logger.info(
                    f" {record.data['ID']}".ljust(PAD, " ")
                    + "recorded as not_available"
                )
            else:
                record.set_status(target_state=colrev.record.RecordState.pdf_prepared)

                record.add_data_provenance(
                    key="file", source="pdf-get-man", note="not_available"
                )

                self.review_manager.report_logger.info(
                    f" {record.data['ID']}".ljust(PAD, " ")
                    + "recorded as not_available (and moved to screen)"
                )
                self.review_manager.logger.info(
                    f" {record.data['ID']}".ljust(PAD, " ")
                    + "recorded as not_available (and moved to screen)"
                )

        record_dict = record.get_data()
        self.review_manager.dataset.save_records_dict(
            records={record_dict["ID"]: record_dict}, partial=True
        )
        self.review_manager.dataset.add_record_changes()

    def main(self) -> None:
        """Get PDFs manually (main entrypoint)"""

        if self.review_manager.in_ci_environment():
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="colrev pdf-get-man",
                detailed_trace="pdf-get-man not available in ci environment",
            )

        records = self.review_manager.dataset.load_records_dict()

        package_manager = self.review_manager.get_package_manager()
        self.pdf_get_man_package_endpoints: dict[
            str, typing.Any
        ] = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.pdf_get_man,
            selected_packages=self.review_manager.settings.pdf_get.pdf_get_man_package_endpoints,
            operation=self,
        )

        for (
            pdf_get_man_package_endpoint
        ) in self.review_manager.settings.pdf_get.pdf_get_man_package_endpoints:
            endpoint = self.pdf_get_man_package_endpoints[
                pdf_get_man_package_endpoint["endpoint"]
            ]

            records = endpoint.pdf_get_man(self, records)  # type: ignore


if __name__ == "__main__":
    pass
