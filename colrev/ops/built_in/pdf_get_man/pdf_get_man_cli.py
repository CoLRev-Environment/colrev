#! /usr/bin/env python
"""CLI interface for manual retrieval of PDFs"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.pdf_get
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_get_man


# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


@zope.interface.implementer(
    colrev.env.package_manager.PDFGetManPackageEndpointInterface
)
@dataclass
class CoLRevCLIPDFGetMan(JsonSchemaMixin):

    """Get PDFs manually based on a CLI"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.__get_from_downloads_folder = False

    def __get_pdf_from_google(
        self,
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,
        record: colrev.record.Record,
    ) -> colrev.record.Record:
        # import webbrowser

        title = record.data.get("title", "no title")
        title = urllib.parse.quote_plus(title)
        url = f"https://www.google.com/search?q={title}+filetype%3Apdf"
        # webbrowser.open_new_tab(url)
        print(url)
        return record

    def __ask_authors_for_pdf(
        self,
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,
        record: colrev.record.Record,
    ) -> colrev.record.Record:
        # get the recipient email(s) from the local author index
        recipient = "TODO"
        subject = f"Copy of a PDF ({record.data['ID']})"

        author_name = record.data.get("author", "").split(",")[0]
        signed, _ = pdf_get_man_operation.review_manager.get_committer()

        template = colrev.env.utils.get_template(
            template_path="template/ops/pdf_get_man_mail.txt"
        )

        content = template.render(record=record, author_name=author_name, signed=signed)

        print("\n\n")
        print(recipient)
        print(subject)
        print("\n\n")
        print(content)
        print("\n\n")

        # next steps: better integration with email clients

        return record

    def __get_filepath(
        self,
        *,
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,
        record: colrev.record.Record,
    ) -> Path:
        filepath = (
            pdf_get_man_operation.review_manager.pdf_dir
            / f"{record.data.get('year', 'NA')}/{record.data['ID']}.pdf"
        )
        if filepath.is_file():
            return filepath

        if "volume" in record.data:
            filepath = (
                pdf_get_man_operation.review_manager.pdf_dir
                / f"{record.data['volume']}/{record.data['ID']}.pdf"
            )
            if filepath.is_file():
                return filepath

        if "volume" in record.data and "number" in record.data:
            filepath = (
                pdf_get_man_operation.review_manager.pdf_dir
                / f"{record.data['volume']}_{record.data['number']}/{record.data['ID']}.pdf"
            )
            if filepath.is_file():
                return filepath

            filepath = (
                pdf_get_man_operation.review_manager.pdf_dir
                / f"{record.data['volume']}/{record.data['number']}/{record.data['ID']}.pdf"
            )
            if filepath.is_file():
                return filepath

        filepath = (
            pdf_get_man_operation.review_manager.pdf_dir / f"{record.data['ID']}.pdf"
        )

        return filepath

    def __retrieve_record_from_downloads_folder(
        self,
        *,
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,
        record: colrev.record.Record,
    ) -> None:
        downloads_folder = Path.home() / Path("Downloads")
        pdfs_in_downloads_folder = list(downloads_folder.glob("*.pdf"))

        if len(pdfs_in_downloads_folder) == 0:
            print("No PDF found in downloads_folder")
            return
        if (
            len(pdfs_in_downloads_folder) > 1
            and not (downloads_folder / Path(f"{record.data['ID']}.pdf")).is_file()
        ):
            print("Multiple PDFs found in downloads_folder (skipping)")
            return

        if Path(f"{record.data['ID']}.pdf").is_file():
            pdf_in_downloads_folder = downloads_folder / Path(
                f"{record.data['ID']}.pdf"
            )
        else:
            pdf_in_downloads_folder = pdfs_in_downloads_folder[0]

        # simple heuristics:
        vol_slash_nr_path = pdf_get_man_operation.review_manager.pdf_dir / Path(
            f"{record.data.get('volume', 'NA')}/{record.data.get('number', 'NA')}"
        )
        if vol_slash_nr_path.is_dir():
            pdf_in_downloads_folder.rename(
                vol_slash_nr_path / Path(f"{record.data['ID']}.pdf")
            )
            return

        vol_underscore_nr_path = pdf_get_man_operation.review_manager.pdf_dir / Path(
            f"{record.data.get('volume', 'NA')}_{record.data.get('number', 'NA')}"
        )
        if vol_underscore_nr_path.is_dir():
            pdf_in_downloads_folder.rename(
                vol_underscore_nr_path / Path(f"{record.data['ID']}.pdf")
            )
            return

        vol_path = pdf_get_man_operation.review_manager.pdf_dir / Path(
            f"{record.data.get('volume', 'NA')}"
        )
        if vol_path.is_dir():
            pdf_in_downloads_folder.rename(vol_path / Path(f"{record.data['ID']}.pdf"))
            return

        year_path = pdf_get_man_operation.review_manager.pdf_dir / Path(
            f"{record.data.get('year', 'NA')}"
        )
        if year_path.is_dir():
            pdf_in_downloads_folder.rename(year_path / Path(f"{record.data['ID']}.pdf"))
            return

        pdf_in_downloads_folder.rename(
            pdf_get_man_operation.review_manager.pdf_dir
            / Path(f"{record.data['ID']}.pdf")
        )

    def __pdf_get_man_record_cli(
        self,
        *,
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan,
        record: colrev.record.Record,
    ) -> None:
        # pdf_get_man_operation.review_manager.logger.debug(
        #     f"called pdf_get_man_cli for {record}"
        # )

        # to print only the essential information
        colrev.record.Record(data=record.get_data()).print_prescreen_record()

        if (
            colrev.record.RecordState.pdf_needs_manual_retrieval
            != record.data["colrev_status"]
        ):
            return

        retrieval_scripts = {
            "get_pdf_from_google": self.__get_pdf_from_google,
            "ask_authors": self.__ask_authors_for_pdf
            # 'get_pdf_from_researchgate': get_pdf_from_researchgate,
        }

        filepath = self.__get_filepath(
            pdf_get_man_operation=pdf_get_man_operation, record=record
        )
        for (
            script_name,  # pylint: disable=unused-variable
            retrieval_script,
        ) in retrieval_scripts.items():
            # pdf_get_man_operation.review_manager.logger.debug(
            #     f'{script_name}({record.data["ID"]}) called'
            # )
            record = retrieval_script(pdf_get_man_operation, record)

            if input("Retrieved (y/n)?") == "y":
                if self.__get_from_downloads_folder:
                    self.__retrieve_record_from_downloads_folder(
                        pdf_get_man_operation=pdf_get_man_operation, record=record
                    )
                filepath = self.__get_filepath(
                    pdf_get_man_operation=pdf_get_man_operation, record=record
                )
                if not filepath.is_file():
                    print(f'File does not exist: {record.data["ID"]}.pdf')
                else:
                    filepath = self.__get_filepath(
                        pdf_get_man_operation=pdf_get_man_operation, record=record
                    )
                    pdf_get_man_operation.pdf_get_man_record(
                        record=record,
                        filepath=filepath,
                    )
                    break

        if not filepath.is_file():
            if input("Is the PDF available (y/n)?") == "n":
                pdf_get_man_operation.pdf_get_man_record(
                    record=record,
                    filepath=None,
                )

        pdf_get_man_operation.review_manager.update_status_yaml()

    def pdf_get_man(
        self, pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan, records: dict
    ) -> dict:
        """Get the PDF manually based on a cli"""

        pdf_get_man_operation.review_manager.logger.info("Retrieve PDFs manually")
        pdf_get_operation = pdf_get_man_operation.review_manager.get_pdf_get_operation()
        pdf_dir = pdf_get_man_operation.review_manager.pdf_dir

        records = pdf_get_man_operation.review_manager.dataset.load_records_dict()
        if input("Check existing unlinked PDFs (y/n)?") == "y":
            records = pdf_get_operation.check_existing_unlinked_pdfs(records=records)

        if input("Get PDF from Downloads folder (y/n)?") == "y":
            self.__get_from_downloads_folder = True

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

            print(f"\n\n{stat}")

            self.__pdf_get_man_record_cli(
                pdf_get_man_operation=pdf_get_man_operation, record=record
            )

        if pdf_get_man_operation.review_manager.dataset.has_changes():
            if input("Create commit (y/n)?") == "y":
                pdf_get_man_operation.review_manager.create_commit(
                    msg="Retrieve PDFs manually",
                    manual_author=True,
                )
        else:
            pdf_get_man_operation.review_manager.logger.info(
                "Retrieve PDFs manually and copy the files to "
                f"the {pdf_dir}. Afterwards, use "
                "colrev pdf-get-man"
            )

        return records


if __name__ == "__main__":
    pass
