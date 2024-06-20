#! /usr/bin/env python
"""CoLRev pdf_get_man operation: Get PDF documents manually."""
from __future__ import annotations

import csv
import typing
from pathlib import Path

import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.record.record
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState


class PDFGetMan(colrev.process.operation.Operation):
    """Get PDFs manually"""

    pdf_get_man_package_endpoints: dict[str, typing.Any]
    MISSING_PDF_FILES_RELATIVE = Path("data/pdf_get_man/missing_pdf_files.csv")

    type = OperationsType.pdf_get_man

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.missing_pdf_files_csv = (
            self.review_manager.path / self.MISSING_PDF_FILES_RELATIVE
        )
        self.verbose = True

    def get_pdf_get_man(self, records: dict) -> list:
        """Get the records that are missing a PDF"""
        missing_records = []
        for record in records.values():
            if record[Fields.STATUS] == RecordState.pdf_needs_manual_retrieval:
                missing_records.append(record)
        return missing_records

    def export_retrieval_table(self, records: dict) -> None:
        """Export a table for manual PDF retrieval"""

        missing_records = self.get_pdf_get_man(records)

        if len(missing_records) > 0:
            missing_records_df = pd.DataFrame.from_records(missing_records)
            # pylint: disable=duplicate-code
            col_order = [
                Fields.ID,
                Fields.AUTHOR,
                Fields.TITLE,
                Fields.JOURNAL,
                Fields.BOOKTITLE,
                Fields.YEAR,
                Fields.VOLUME,
                Fields.NUMBER,
                Fields.PAGES,
                Fields.DOI,
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
            record = colrev.record.record.Record(record_dict)
            if record.data[Fields.STATUS] == RecordState.pdf_needs_manual_retrieval:
                record.set_status(RecordState.pdf_not_available)
        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(
            msg="Discard missing PDFs", manual_author=True
        )

    def get_data(self) -> dict:
        """Get the data for pdf-get-man"""
        # pylint: disable=duplicate-code

        pdf_dir = self.review_manager.paths.pdf
        pdf_dir.mkdir(exist_ok=True)

        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        nr_tasks = len(
            [
                x
                for x in record_header_list
                if RecordState.pdf_needs_manual_retrieval == x[Fields.STATUS]
            ]
        )
        pad = min((max(len(x[Fields.ID]) for x in record_header_list) + 2), 40)
        items = self.review_manager.dataset.read_next_record(
            conditions=[{Fields.STATUS: RecordState.pdf_needs_manual_retrieval}]
        )
        pdf_get_man_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(pdf_get_man_data)
        )
        return pdf_get_man_data

    def pdfs_retrieved_manually(self) -> bool:
        """Check whether PDFs were retrieved manually"""
        return self.review_manager.dataset.has_record_changes()

    def pdf_get_man_record(
        self,
        *,
        record: colrev.record.record.Record,
        filepath: typing.Optional[Path] = None,
        PAD: int = 40,
    ) -> None:
        """Record pdf-get-man decision"""
        if filepath is not None:
            record.set_status(RecordState.pdf_imported)
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
                record.set_status(RecordState.pdf_not_available)
                self.review_manager.report_logger.info(
                    f" {record.data['ID']}".ljust(PAD, " ")
                    + "recorded as not_available"
                )
                self.review_manager.logger.info(
                    f" {record.data['ID']}".ljust(PAD, " ")
                    + "recorded as not_available"
                )
            else:
                record.set_status(RecordState.pdf_prepared)

                record.add_field_provenance(
                    key=Fields.FILE, source="pdf-get-man", note="not_available"
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
            {record_dict[Fields.ID]: record_dict}, partial=True
        )

    @colrev.process.operation.Operation.decorate()
    def main(self) -> None:
        """Get PDFs manually (main entrypoint)"""

        if (
            self.review_manager.in_ci_environment()
            and not self.review_manager.in_test_environment()
        ):
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="colrev pdf-get-man",
                detailed_trace="pdf-get-man not available in ci environment",
            )

        records = self.review_manager.dataset.load_records_dict()
        pdf_get_man_package_endpoints = (
            self.review_manager.settings.pdf_get.pdf_get_man_package_endpoints
        )

        package_manager = self.review_manager.get_package_manager()

        for pdf_get_man_package_endpoint in pdf_get_man_package_endpoints:
            pdf_get_man_class = package_manager.get_package_endpoint_class(
                package_type=EndpointType.pdf_get_man,
                package_identifier=pdf_get_man_package_endpoint["endpoint"],
            )
            endpoint = pdf_get_man_class(
                pdf_get_man_operation=self, settings=pdf_get_man_package_endpoint
            )

            records = endpoint.pdf_get_man(records)  # type: ignore
