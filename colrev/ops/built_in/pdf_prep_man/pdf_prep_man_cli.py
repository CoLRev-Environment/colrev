#! /usr/bin/env python
"""CLI interface for manual preparation of PDFs"""
from __future__ import annotations

import os
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.record
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_prep_man


# pylint: disable=too-few-public-methods


@zope.interface.implementer(
    colrev.env.package_manager.PDFPrepManPackageEndpointInterface
)
@dataclass
class CoLRevCLIPDFManPrep(JsonSchemaMixin):
    """Manually prepare PDFs based on a CLI (not yet implemented)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_prep_man_operation: colrev.ops.pdf_prep_man.PDFPrepMan,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __update_metadata(
        self, *, record: colrev.record.Record
    ) -> colrev.record.Record:
        valid_selections = ["a", "c", "t", "v", "n", "p", "s"]
        user_selection = ""
        print(
            "Update metadata fields: "
            "(a)uthor, (c)ontainer title, (t)itle, (v)olume, (n)umber, (p)ages  or (s)ave"
        )
        while user_selection not in valid_selections:
            user_selection = input("Selection: ")

            if user_selection == "s":
                break
            if user_selection == "a":
                author = input("Authors:")
                record.update_field(
                    key="author", value=author, source="manual_correction"
                )
            elif user_selection == "c":
                if "journal" in record.data:
                    journal = input("Journal:")
                    record.update_field(
                        key="journal", value=journal, source="manual_correction"
                    )
                if "booktitle" in record.data:
                    booktitle = input("Booktitle:")
                    record.update_field(
                        key="booktitle", value=booktitle, source="manual_correction"
                    )
            elif user_selection == "t":
                title = input("Title:")
                record.update_field(
                    key="title", value=title, source="manual_correction"
                )
            elif user_selection == "v":
                volume = input("Volume:")
                record.update_field(
                    key="volume", value=volume, source="manual_correction"
                )
            elif user_selection == "n":
                number = input("Number:")
                record.update_field(
                    key="number", value=number, source="manual_correction"
                )
            elif user_selection == "p":
                pages = input("Pages:")
                record.update_field(
                    key="pages", value=pages, source="manual_correction"
                )
            user_selection = ""

        return record

    def pdf_prep_man(
        self, pdf_prep_man_operation: colrev.ops.pdf_prep_man.PDFPrepMan, records: dict
    ) -> dict:
        """Prepare PDF manually based on a cli"""

        # pylint: disable=too-many-statements
        to_skip = 0

        def man_pdf_prep(
            pdf_prep_man: colrev.ops.pdf_prep_man.PDFPrepMan,
            records: dict,
            item: dict,
            stat: str,
        ) -> dict:
            # pylint: disable=no-member
            # pylint: disable=too-many-branches
            # pylint: disable=too-many-locals

            current_platform = platform.system()
            if current_platform in ["Linux", "Darwin"]:
                os.system("clear")
            else:
                os.system("cls")

            print(stat)
            record = colrev.record.Record(data=item)
            record.print_pdf_prep_man()

            record_dict = records[item["ID"]]
            record = colrev.record.Record(data=record_dict)
            if (
                colrev.record.RecordState.pdf_needs_manual_preparation
                != record_dict["colrev_status"]
            ):
                return record_dict

            file_provenance = record.get_field_provenance(key="file")
            print(
                "Manual preparation needed:"
                f" {colors.RED}{file_provenance['note']}{colors.END}"
            )

            filepath = pdf_prep_man.review_manager.path / Path(record_dict["file"])
            if not filepath.is_file():
                filepath = (
                    pdf_prep_man.review_manager.pdf_dir / f"{record_dict['ID']}.pdf"
                )
            record.data.update(
                colrev_pdf_id=record.get_colrev_pdf_id(pdf_path=filepath)
            )
            if filepath.is_file():
                current_platform = platform.system()
                if current_platform == "Linux":
                    subprocess.call(["xdg-open", filepath])
                else:
                    os.startfile(filepath)  # type: ignore

                # if PDF > 100 pages, we may check on which page we find the title & print

                intro_paragraph = (
                    "Prepared?\n"
                    "       (y)es, \n"
                    "       (n)o/delete file,\n"
                    "       (s)kip, (s10) to skip 10 records, or (q)uit,\n"
                    "       (c)overpage remove, (l)ast page remove, (r)emove page range, "
                    "(m)etadata needs to be updated\n"
                )
                print(intro_paragraph)
                user_selection = ""
                valid_selections = ["y", "n", "s", "q"]
                while user_selection not in valid_selections:
                    user_selection = input("Selection: ")
                    if user_selection.startswith("s"):
                        if user_selection[1:].isdigit():
                            nonlocal to_skip
                            to_skip = int(user_selection[1:])
                        return records
                    if user_selection == "q":
                        raise QuitPressedException()

                    if user_selection == "m":
                        self.__update_metadata(record=record)
                        print(intro_paragraph)
                    elif user_selection == "c":
                        try:
                            pdf_prep_man_operation.extract_coverpage(filepath=filepath)
                        except colrev_exceptions.InvalidPDFException:
                            pass
                    elif user_selection == "l":
                        try:
                            pdf_prep_man_operation.extract_lastpage(filepath=filepath)
                        except colrev_exceptions.InvalidPDFException:
                            pass
                    elif user_selection == "r":
                        range_str = ""
                        while not re.match(r"(\d)+-(\d)+", range_str):
                            range_str = input('Page range to remove (e.g., "0-10"):')

                        pages_to_exclude = list(
                            range(
                                int(range_str[: range_str.find("-")]),
                                int(range_str[range_str.find("-") + 1 :]),
                            )
                        )
                        try:
                            pdf_prep_man_operation.extract_pages(
                                filepath=filepath, pages_to_remove=pages_to_exclude
                            )
                        except colrev_exceptions.InvalidPDFException:
                            pass

                    elif user_selection == "y":
                        pdf_prep_man_operation.set_pdf_man_prepared(record=record)
                    elif user_selection == "n":
                        record.remove_field(key="file")
                        record.set_status(
                            target_state=colrev.record.RecordState.pdf_needs_manual_retrieval
                        )
                        if filepath.is_file():
                            filepath.unlink()
                    else:
                        print("Invalid selection.")

            else:
                print(f'File does not exist ({record.data["ID"]})')

            pdf_prep_man.review_manager.dataset.save_records_dict(records=records)

            return records

        pdf_prep_man_operation.review_manager.logger.info(
            "Loading data for pdf_prep_man"
        )
        pdf_prep_man_data = pdf_prep_man_operation.get_data()
        records = pdf_prep_man_operation.review_manager.dataset.load_records_dict()

        for i, item in enumerate(pdf_prep_man_data["items"]):
            if to_skip > 0:
                to_skip -= 1
                continue
            try:
                stat = str(i + 1) + "/" + str(pdf_prep_man_data["nr_tasks"])
                records = man_pdf_prep(pdf_prep_man_operation, records, item, stat)
            except QuitPressedException:
                break

        pdf_prep_man_operation.review_manager.dataset.save_records_dict(records=records)
        pdf_prep_man_operation.review_manager.dataset.add_record_changes()

        if pdf_prep_man_operation.pdfs_prepared_manually():
            if input("Create commit (y/n)?") == "y":
                pdf_prep_man_operation.review_manager.create_commit(
                    msg="Prepare PDFs manually",
                    manual_author=True,
                )
        else:
            pdf_prep_man_operation.review_manager.logger.info(
                "Prepare PDFs manually. Afterwards, use colrev pdf-get-man"
            )

        return records


class QuitPressedException(Exception):
    """Quit-pressed exception"""


if __name__ == "__main__":
    pass
