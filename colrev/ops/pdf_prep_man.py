#! /usr/bin/env python
"""CoLRev pdf_prep_man operation: Prepare PDF documents manually."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter
from PyPDF2.errors import PdfReadError

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record


class PDFPrepMan(colrev.operation.Operation):
    """Prepare PDFs manually"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.pdf_prep_man,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.verbose = True

    def discard(self) -> None:
        """Discard records whose PDFs need manual preparation (set to pdf_not_available)"""

        records = self.review_manager.dataset.load_records_dict()
        for record_dict in records.values():
            if (
                record_dict["colrev_status"]
                == colrev.record.RecordState.pdf_needs_manual_preparation
            ):
                record = colrev.record.Record(data=record_dict)
                record.set_status(
                    target_state=colrev.record.RecordState.pdf_not_available
                )
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
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
                if colrev.record.RecordState.pdf_needs_manual_preparation
                == x["colrev_status"]
            ]
        )
        pad = min((max(len(x["ID"]) for x in record_header_list) + 2), 40)

        items = self.review_manager.dataset.read_next_record(
            conditions=[
                {
                    "colrev_status": colrev.record.RecordState.pdf_needs_manual_preparation
                }
            ]
        )
        pdf_prep_man_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(pdf_prep_man_data)
        )
        return pdf_prep_man_data

    def pdfs_prepared_manually(self) -> bool:
        """Check whether PDFs were prepared manually"""
        return self.review_manager.dataset.has_changes()

    def pdf_prep_man_stats(self) -> None:
        """Determine PDF prep man statistics"""
        # pylint: disable=duplicate-code

        self.review_manager.logger.info(
            f"Load {self.review_manager.dataset.RECORDS_FILE_RELATIVE}"
        )
        records = self.review_manager.dataset.load_records_dict()

        self.review_manager.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}

        prep_man_hints = []
        crosstab = []
        for record_dict in records.values():
            if (
                colrev.record.RecordState.pdf_needs_manual_preparation
                != record_dict["colrev_status"]
            ):
                continue

            if record_dict["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = 1

            record = colrev.record.Record(data=record_dict)
            prov_d = record.data["colrev_data_provenance"]

            if "file" in prov_d:
                if prov_d["file"]["note"] != "":
                    for hint in prov_d["file"]["note"].split(","):
                        prep_man_hints.append(hint.lstrip())

            for hint in prep_man_hints:
                crosstab.append([record_dict["journal"], hint.lstrip()])

        crosstab_df = pd.DataFrame(crosstab, columns=["journal", "hint"])

        if crosstab_df.empty:
            print("No records to prepare manually.")
        else:
            # pylint: disable=duplicate-code
            tabulated = pd.pivot_table(
                crosstab_df[["journal", "hint"]],
                index=["journal"],
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
            f"Load {self.review_manager.dataset.RECORDS_FILE_RELATIVE}"
        )
        records = self.review_manager.dataset.load_records_dict()

        records = {
            record["ID"]: record
            for record in records.values()
            if colrev.record.RecordState.pdf_needs_manual_preparation
            == record["colrev_status"]
        }
        self.review_manager.dataset.save_records_dict_to_file(
            records=records, save_path=prep_bib_path
        )

        bib_db_df = pd.DataFrame.from_records(list(records.values()))

        # pylint: disable=duplicate-code
        col_names = [
            "ID",
            "colrev_origin",
            "author",
            "title",
            "year",
            "journal",
            # "booktitle",
            "volume",
            "number",
            "pages",
            "doi",
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

            with open("data/pdf-prep-records.bib", encoding="utf8") as target_db:
                records_changed_dict = self.review_manager.dataset.load_records_dict(
                    load_str=target_db.read()
                )
                records_changed = list(records_changed_dict.values())

        records = self.review_manager.dataset.load_records_dict()
        for record in records.values():
            # IDs may change - matching based on origins
            changed_record_l = [
                x
                for x in records_changed
                if x["colrev_origin"] == record["colrev_origin"]
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

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.check_repo()

    def extract_coverpage(self, *, filepath: Path) -> None:
        """Extract coverpage from PDF"""

        local_index = self.review_manager.get_local_index()
        cp_path = local_index.local_environment_path / Path(".coverpages")
        cp_path.mkdir(exist_ok=True)

        try:
            pdf_reader = PdfFileReader(str(filepath), strict=False)
            writer_cp = PdfFileWriter()
            writer_cp.addPage(pdf_reader.getPage(0))
            writer = PdfFileWriter()
            for i in range(1, len(pdf_reader.pages)):
                writer.addPage(pdf_reader.getPage(i))
            with open(filepath, "wb") as outfile:
                writer.write(outfile)
            with open(cp_path / filepath.name, "wb") as outfile:
                writer_cp.write(outfile)
        except PdfReadError as exc:
            raise colrev_exceptions.InvalidPDFException(filepath) from exc

    def extract_lastpage(self, *, filepath: Path) -> None:
        """Extract last page from PDF"""

        local_index = self.review_manager.get_local_index()
        lp_path = local_index.local_environment_path / Path(".lastpages")
        lp_path.mkdir(exist_ok=True)

        try:
            pdf_reader = PdfFileReader(str(filepath), strict=False)
            writer_lp = PdfFileWriter()
            writer_lp.addPage(pdf_reader.getPage(len(pdf_reader.pages) - 1))
            writer = PdfFileWriter()
            for i in range(0, len(pdf_reader.pages) - 1):
                writer.addPage(pdf_reader.getPage(i))
            with open(filepath, "wb") as outfile:
                writer.write(outfile)
            with open(lp_path / filepath.name, "wb") as outfile:
                writer_lp.write(outfile)
        except PdfReadError as exc:
            raise colrev_exceptions.InvalidPDFException(filepath) from exc

    def extract_pages(self, *, filepath: Path, pages_to_remove: list) -> None:
        """Extract pages from PDF"""

        try:
            pdf_reader = PdfFileReader(str(filepath), strict=False)
            pages_to_add = [
                x
                for x in list(range(0, len(pdf_reader.pages)))
                if x not in pages_to_remove
            ]
            writer = PdfFileWriter()
            for i in pages_to_add:
                writer.addPage(pdf_reader.getPage(i))
            with open(filepath, "wb") as outfile:
                writer.write(outfile)

        except PdfReadError as exc:
            raise colrev_exceptions.InvalidPDFException(filepath) from exc

    def set_pdf_man_prepared(self, *, record: colrev.record.Record) -> None:
        """Set the PDF to manually prepared"""

        record.set_status(target_state=colrev.record.RecordState.pdf_prepared)
        record.reset_pdf_provenance_notes()

        pdf_path = Path(self.review_manager.path / Path(record.data["file"]))
        prev_cpid = record.data.get("colrev_pdf_id", "NA")
        record.data.update(colrev_pdf_id=record.get_colrev_pdf_id(pdf_path=pdf_path))
        if prev_cpid != record.data.get("colrev_pdf_id", "NA"):
            record.add_data_provenance(key="file", source="manual")

        record_dict = record.get_data()
        self.review_manager.dataset.save_records_dict(
            records={record_dict["ID"]: record_dict}, partial=True
        )
        self.review_manager.dataset.add_changes(
            path=self.review_manager.dataset.RECORDS_FILE_RELATIVE
        )

    def main(self) -> None:
        """Prepare PDFs manually (main entrypoint)"""

        if self.review_manager.in_ci_environment():
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
            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep_man,
                selected_packages=pdf_prep_man_package_endpoints,
                operation=self,
            )

            endpoint = endpoint_dict[pdf_prep_man_package_endpoint["endpoint"]]

            records = endpoint.pdf_prep_man(self, records)  # type: ignore


if __name__ == "__main__":
    pass
