#! /usr/bin/env python
"""CLI interface for manual preparation of PDFs"""
from __future__ import annotations

import os
import platform
import pprint
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record
import colrev.ui_cli.cli_colors as colors

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

    def __init__(
        self,
        *,
        pdf_prep_man_operation: colrev.ops.pdf_prep_man.PDFPrepMan,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def pdf_prep_man(
        self, pdf_prep_man_operation: colrev.ops.pdf_prep_man.PDFPrepMan, records: dict
    ) -> dict:
        """Prepare PDF manually based on a cli"""

        # pylint: disable=too-many-statements

        _pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

        def man_pdf_prep(
            pdf_prep_man: colrev.ops.pdf_prep_man.PDFPrepMan,
            records: dict,
            item: dict,
            stat: str,
        ) -> dict:

            # pylint: disable=no-member
            # pylint: disable=too-many-branches

            # pdf_prep_man_operation.review_manager.logger.debug(
            #     f"called man_pdf_prep for {_pp.pformat(item)}"
            # )
            print(stat)
            record = colrev.record.PDFPrepManRecord(data=item)
            print(record)

            record_dict = records[item["ID"]]
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

            filepath = pdf_prep_man.review_manager.pdf_dir / f"{record_dict['ID']}.pdf"
            pdf_path = pdf_prep_man.review_manager.path / Path(record_dict["file"])
            if pdf_path.is_file() or filepath.is_file():
                current_platform = platform.system()
                if current_platform:
                    subprocess.call(["xdg-open", filepath])
                else:
                    os.startfile(filepath)  # type: ignore

                user_selection = ""
                valid_selections = ["y", "n", "r"]
                while user_selection not in valid_selections:

                    user_selection = input(
                        "Prepared? ( (y)es, (n)o/delete file, (s)kip, (r)emove coverpage, (q)uit)?"
                    )
                    if "s" == user_selection:
                        return records
                    if "q" == user_selection:
                        raise QuitPressedException()

                    if "r" == user_selection:
                        pdf_prep_man_operation.extract_coverpage(filepath=pdf_path)
                        user_selection = "y"

                    if "y" == user_selection:
                        record = colrev.record.PDFPrepManRecord(data=record_dict)
                        record.set_pdf_man_prepared(
                            review_manager=pdf_prep_man.review_manager
                        )

                    elif "n" == user_selection:
                        record = colrev.record.PDFPrepManRecord(data=record_dict)
                        record.remove_field(key="file")
                        record.set_status(
                            target_state=colrev.record.RecordState.pdf_needs_manual_retrieval
                        )
                        if pdf_path.is_file():
                            pdf_path.unlink()
                        if filepath.is_file():
                            filepath.unlink()

            else:
                print(f'File does not exist ({record.data["ID"]})')

            pdf_prep_man.review_manager.dataset.save_records_dict(records=records)

            return records

        saved_args = locals()

        pdf_prep_man_data = pdf_prep_man_operation.get_data()
        records = pdf_prep_man_operation.review_manager.dataset.load_records_dict()

        for i, item in enumerate(pdf_prep_man_data["items"]):
            try:
                stat = str(i + 1) + "/" + str(pdf_prep_man_data["nr_tasks"])
                records = man_pdf_prep(pdf_prep_man_operation, records, item, stat)
            except QuitPressedException:
                break

        pdf_prep_man_operation.review_manager.dataset.save_records_dict(records=records)
        pdf_prep_man_operation.review_manager.dataset.add_record_changes()

        if pdf_prep_man_operation.pdfs_prepared_manually():
            if "y" == input("Create commit (y/n)?"):

                pdf_prep_man_operation.review_manager.create_commit(
                    msg="Prepare PDFs manually",
                    manual_author=True,
                    saved_args=saved_args,
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
