#! /usr/bin/env python
"""CoLRev pdf_prep_man operation: Prepare PDF documents manually."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pymupdf

import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.record.record
import colrev.record.record_pdf
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.constants import OperationsType
from colrev.constants import RecordState
from colrev.writer.write_utils import write_file


class PDFPrepMan(colrev.process.operation.Operation):
    """Prepare PDFs manually"""

    type = OperationsType.pdf_prep_man

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

        self.verbose = True

    def discard(self) -> None:
        """Discard records whose PDFs need manual preparation (set to pdf_not_available)"""

        records = self.review_manager.dataset.load_records_dict()
        for record_dict in records.values():
            if record_dict[Fields.STATUS] == RecordState.pdf_needs_manual_preparation:
                record = colrev.record.record.Record(record_dict)
                record.set_status(RecordState.pdf_not_available)
        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(
            msg="Discard man-prep PDFs", manual_author=True
        )

    def get_data(self) -> dict:
        """Get the data for PDF prep man"""
        # pylint: disable=duplicate-code

        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        nr_tasks = len(
            [
                x
                for x in record_header_list
                if RecordState.pdf_needs_manual_preparation == x[Fields.STATUS]
            ]
        )
        pad = 0
        if record_header_list:
            pad = min((max(len(x[Fields.ID]) for x in record_header_list) + 2), 40)

        items = self.review_manager.dataset.read_next_record(
            conditions=[{Fields.STATUS: RecordState.pdf_needs_manual_preparation}]
        )
        pdf_prep_man_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(pdf_prep_man_data)
        )
        return pdf_prep_man_data

    def pdfs_prepared_manually(self) -> bool:
        """Check whether PDFs were prepared manually"""
        return self.review_manager.dataset.has_record_changes()

    def pdf_prep_man_stats(self) -> None:
        """Determine PDF prep man statistics"""
        # pylint: disable=duplicate-code

        self.review_manager.logger.info(
            f"Load {self.review_manager.paths.RECORDS_FILE}"
        )
        records = self.review_manager.dataset.load_records_dict()

        self.review_manager.logger.info("Calculate statistics")
        stats: dict = {Fields.ENTRYTYPE: {}}

        prep_man_hints = []
        crosstab = []
        for record_dict in records.values():
            if RecordState.pdf_needs_manual_preparation != record_dict[Fields.STATUS]:
                continue

            if record_dict[Fields.ENTRYTYPE] in stats[Fields.ENTRYTYPE]:
                stats[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]] = (
                    stats[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]] + 1
                )
            else:
                stats[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]] = 1

            record = colrev.record.record.Record(record_dict)
            prov_d = record.data[Fields.D_PROV]

            if Fields.FILE in prov_d:
                if prov_d[Fields.FILE]["note"] != "":
                    for hint in prov_d[Fields.FILE]["note"].split(","):
                        prep_man_hints.append(hint.lstrip())

            for hint in prep_man_hints:
                crosstab.append([record_dict[Fields.JOURNAL], hint.lstrip()])

        crosstab_df = pd.DataFrame(crosstab, columns=[Fields.JOURNAL, "hint"])

        if crosstab_df.empty:
            print("No records to prepare manually.")
        else:
            # pylint: disable=duplicate-code
            tabulated = pd.pivot_table(
                crosstab_df[[Fields.JOURNAL, "hint"]],
                index=[Fields.JOURNAL],
                columns=["hint"],
                aggfunc=len,
                fill_value=0,
                margins=True,
            )
            # .sort_index(axis='columns')
            tabulated.sort_values(by=["All"], ascending=False, inplace=True)
            # Transpose because we tend to have more error categories than search files.
            tabulated = tabulated.transpose()
            print(tabulated)
            self.review_manager.logger.info(
                "Writing data to file: manual_preparation_statistics.csv"
            )
            tabulated.to_csv("manual_pdf_preparation_statistics.csv")

    def extract_needs_pdf_prep_man(self) -> None:
        """Apply PDF prep man to csv/bib"""

        prep_bib_path = self.review_manager.path / Path("data/pdf-prep-records.bib")
        prep_csv_path = self.review_manager.path / Path("data/pdf-prep-records.csv")

        if prep_csv_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_csv_path})")
            return

        if prep_bib_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_bib_path})")
            return

        self.review_manager.logger.info(
            f"Load {self.review_manager.paths.RECORDS_FILE}"
        )
        records = self.review_manager.dataset.load_records_dict()

        records = {
            record[Fields.ID]: record
            for record in records.values()
            if RecordState.pdf_needs_manual_preparation == record[Fields.STATUS]
        }

        write_file(records_dict=records, filename=prep_bib_path)

        bib_db_df = pd.DataFrame.from_records(list(records.values()))

        # pylint: disable=duplicate-code
        col_names = [
            Fields.ID,
            Fields.ORIGIN,
            Fields.AUTHOR,
            Fields.TITLE,
            Fields.YEAR,
            Fields.JOURNAL,
            # Fields.BOOKTITLE,
            Fields.VOLUME,
            Fields.NUMBER,
            Fields.PAGES,
            Fields.DOI,
        ]
        for col_name in col_names:
            if col_name not in bib_db_df:
                bib_db_df[col_name] = "NA"
        bib_db_df = bib_db_df[col_names]

        bib_db_df.to_csv(prep_csv_path, index=False)
        self.review_manager.logger.info(f"Created {prep_csv_path.name}")

    def apply_pdf_prep_man(self) -> None:
        """Apply PDF prep man from csv/bib"""

        if Path("data/pdf-prep-records.csv").is_file():
            self.review_manager.logger.info("Load prep-records.csv")
            bib_db_df = pd.read_csv("data/pdf-prep-records.csv")
            records_changed = bib_db_df.to_dict("records")

        if Path("data/pdf-prep-records.bib").is_file():
            self.review_manager.logger.info("Load prep-records.bib")

            records_changed = colrev.loader.load_utils.load(
                filename=Path("data/pdf-prep-records.bib"),
                logger=self.review_manager.logger,
            )

        records = self.review_manager.dataset.load_records_dict()
        for record in records.values():
            # IDs may change - matching based on origins
            changed_record_l = [
                x for x in records_changed if x[Fields.ORIGIN] == record[Fields.ORIGIN]
            ]
            if len(changed_record_l) == 1:
                changed_record = changed_record_l.pop()
                for key, value in changed_record.items():
                    # if record['ID'] == 'Alter2014':
                    #     print(key, value)
                    if str(value) == "nan":
                        if key in record:
                            del record[key]
                        continue
                    record[key] = value
                    if value == "":
                        del record[key]

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.check_repo()

    def extract_coverpage(self, *, filepath: Path) -> None:
        """Extract coverpage from PDF"""

        cp_path = Filepaths.LOCAL_ENVIRONMENT_DIR / Path(".coverpages")
        cp_path.mkdir(exist_ok=True)

        doc1 = pymupdf.Document(str(filepath))
        if doc1.page_count > 0:
            colrev.record.record_pdf.PDFRecord.extract_pages_from_pdf(
                pages=[0],
                pdf_path=filepath,
                save_to_path=cp_path,
            )

    def extract_lastpage(self, *, filepath: Path) -> None:
        """Extract last page from PDF"""

        lp_path = Filepaths.LOCAL_ENVIRONMENT_DIR / Path(".lastpages")
        lp_path.mkdir(exist_ok=True)

        doc1 = pymupdf.Document(str(filepath))
        if doc1.page_count > 0:
            colrev.record.record_pdf.PDFRecord.extract_pages_from_pdf(
                pages=[doc1.page_count - 1],
                pdf_path=filepath,
                save_to_path=lp_path,
            )

    def extract_pages(self, *, filepath: Path, pages_to_remove: list) -> None:
        """Extract pages from PDF"""

        doc1 = pymupdf.Document(str(filepath))
        if doc1.page_count > 0:
            colrev.record.record_pdf.PDFRecord.extract_pages_from_pdf(
                pages=pages_to_remove,
                pdf_path=filepath,
            )

    def set_pdf_man_prepared(self, record: colrev.record.record.Record) -> None:
        """Set the PDF to manually prepared"""

        record.set_status(RecordState.pdf_prepared)
        record.reset_pdf_provenance_notes()

        pdf_path = Path(self.review_manager.path / Path(record.data[Fields.FILE]))
        prev_cpid = record.data.get("colrev_pdf_id", "NA")
        record.data.update(colrev_pdf_id=record.get_colrev_pdf_id(pdf_path))
        if prev_cpid != record.data.get("colrev_pdf_id", "NA"):
            record.add_field_provenance(key=Fields.FILE, source="manual")

        record_dict = record.get_data()
        self.review_manager.dataset.save_records_dict(
            {record_dict[Fields.ID]: record_dict}, partial=True
        )
        self.review_manager.dataset.add_changes(self.review_manager.paths.RECORDS_FILE)

    @colrev.process.operation.Operation.decorate()
    def main(self) -> None:
        """Prepare PDFs manually (main entrypoint)"""

        if (
            self.review_manager.in_ci_environment()
            and not self.review_manager.in_test_environment()
        ):
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="colrev pdf-prep-man",
                detailed_trace="pdf-prep-man not available in ci environment",
            )

        records = self.review_manager.dataset.load_records_dict()

        package_manager = self.review_manager.get_package_manager()

        pdf_prep_man_package_endpoints = (
            self.review_manager.settings.pdf_prep.pdf_prep_man_package_endpoints
        )
        for pdf_prep_man_package_endpoint in pdf_prep_man_package_endpoints:

            pdf_prep_man_class = package_manager.get_package_endpoint_class(
                package_type=EndpointType.pdf_prep_man,
                package_identifier=pdf_prep_man_package_endpoint["endpoint"],
            )
            endpoint = pdf_prep_man_class(
                pdf_prep_man_operation=self,
                settings=pdf_prep_man_package_endpoint,
            )

            records = endpoint.pdf_prep_man(records)  # type: ignore
