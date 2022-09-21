#! /usr/bin/env python
"""CLI interface for manual retrieval of PDFs"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.pdf_get
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.pdf_get_man


# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFGetManPackageInterface)
@dataclass
class CoLRevCLIPDFGetMan(JsonSchemaMixin):

    """Get PDFs manually based on a CLI"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,  # pylint: disable=unused-argument
        settings,
    ):
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def get_man_pdf(
        self, pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan, records: dict
    ) -> dict:
        def get_pdf_from_google(record: colrev.record.Record) -> colrev.record.Record:
            # pylint: disable=import-outside-toplevel
            import urllib.parse

            # import webbrowser

            title = record.data.get("title", "no title")
            title = urllib.parse.quote_plus(title)
            url = f"https://www.google.com/search?q={title}+filetype%3Apdf"
            # webbrowser.open_new_tab(url)
            print(url)
            return record

        def pdf_get_man_record_cli(
            *,
            pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,
            record: colrev.record.Record,
        ) -> None:

            pdf_get_man_operation.review_manager.logger.debug(
                f"called pdf_get_man_cli for {record}"
            )

            # to print only the essential information
            print(colrev.record.PrescreenRecord(data=record.get_data()))

            if (
                colrev.record.RecordState.pdf_needs_manual_retrieval
                != record.data["colrev_status"]
            ):
                return

            retrieval_scripts = {
                "get_pdf_from_google": get_pdf_from_google,
                # 'get_pdf_from_researchgate': get_pdf_from_researchgate,
            }

            filepath = (
                pdf_get_man_operation.review_manager.pdf_directory
                / f"{record.data['ID']}.pdf"
            )

            for script_name, retrieval_script in retrieval_scripts.items():
                pdf_get_man_operation.review_manager.logger.debug(
                    f'{script_name}({record.data["ID"]}) called'
                )
                record = retrieval_script(record)

                if "y" == input("Retrieved (y/n)?"):
                    if not filepath.is_file():
                        print(f'File does not exist: {record.data["ID"]}.pdf')
                    else:
                        filepath = (
                            pdf_get_man_operation.review_manager.PDF_DIRECTORY_RELATIVE
                            / f"{record.data['ID']}.pdf"
                        )
                        record.pdf_get_man(
                            review_manager=pdf_get_man_operation.review_manager,
                            filepath=filepath,
                        )
                        break

            if not filepath.is_file():
                if "n" == input("Is the PDF available (y/n)?"):
                    record.pdf_get_man(
                        review_manager=pdf_get_man_operation.review_manager,
                        filepath=None,
                    )

        saved_args = locals()
        pdf_get_man_operation.review_manager.logger.info("Retrieve PDFs manually")
        pdf_get_operation = pdf_get_man_operation.review_manager.get_pdf_get_operation()
        pdf_directory = pdf_get_man_operation.review_manager.pdf_directory

        records = pdf_get_man_operation.review_manager.dataset.load_records_dict()
        records = pdf_get_operation.check_existing_unlinked_pdfs(records=records)

        for record_dict in records.values():
            record = colrev.record.Record(data=record_dict)
            pdf_get_operation.link_pdf(record=record).get_data()

        pdf_get_man_operation.export_retrieval_table(records=records)
        pdf_get_man_data = pdf_get_man_operation.get_data()

        print(
            "\nInstructions\n\n      "
            "Get the pdfs, rename them (ID.pdf) and store them in the pdfs directory.\n"
        )
        input("Enter to start.")

        for i, item in enumerate(pdf_get_man_data["items"]):
            stat = str(i + 1) + "/" + str(pdf_get_man_data["nr_tasks"])

            record = colrev.record.Record(data=records[item["ID"]])

            print(stat)

            pdf_get_man_record_cli(
                pdf_get_man_operation=pdf_get_man_operation, record=record
            )

        if pdf_get_man_operation.review_manager.dataset.has_changes():
            if "y" == input("Create commit (y/n)?"):
                pdf_get_man_operation.review_manager.create_commit(
                    msg="Retrieve PDFs manually",
                    manual_author=True,
                    saved_args=saved_args,
                )
        else:
            pdf_get_man_operation.review_manager.logger.info(
                "Retrieve PDFs manually and copy the files to "
                f"the {pdf_directory}. Afterwards, use "
                "colrev pdf-get-man"
            )

        return records


if __name__ == "__main__":
    pass
