#! /usr/bin/env python
from __future__ import annotations

import pprint
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.process
import colrev.record

if TYPE_CHECKING:
    import colrev.pdf_prep_man.PDFPrepMan


@zope.interface.implementer(colrev.process.PDFPrepManEndpoint)
class CoLRevCLIPDFManPrep:
    def __init__(
        self,
        *,
        pdf_prep_man_operation: colrev.pdf_prep_man.PDFPrepMan,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def prep_man_pdf(
        self, pdf_prep_man_operation: colrev.pdf_prep_man.PDFPrepMan, records: dict
    ) -> dict:

        _pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

        def man_pdf_prep(
            pdf_prep_man: colrev.pdf_prep_man.PDFPrepMan,
            records: dict,
            item,
            stat,
        ) -> dict:

            pdf_prep_man_operation.review_manager.logger.debug(
                f"called man_pdf_prep for {_pp.pformat(item)}"
            )
            print(stat)
            _pp.pprint(item)

            record_dict = records[item["ID"]]
            if (
                colrev.record.RecordState.pdf_needs_manual_preparation
                != record_dict["colrev_status"]
            ):
                return record_dict

            print(
                "Manual preparation needed:"
                f" {record_dict.get('pdf_prep_hints', 'Details not available.')}"
            )

            filepath = (
                pdf_prep_man.review_manager.pdf_directory / f"{record_dict['ID']}.pdf"
            )
            pdf_path = pdf_prep_man.review_manager.path / Path(record_dict["file"])
            if pdf_path.is_file() or filepath.is_file():
                if "y" == input("Prepared? (y/n)?"):
                    record = colrev.record.Record(data=record_dict)
                    record.pdf_man_prep(review_manager=pdf_prep_man.review_manager)

            else:
                print(f'File does not exist ({record.data["ID"]})')

            return records

        saved_args = locals()

        pdf_prep_man_data = pdf_prep_man_operation.get_data()
        records = pdf_prep_man_operation.review_manager.dataset.load_records_dict()

        for i, item in enumerate(pdf_prep_man_data["items"]):
            stat = str(i + 1) + "/" + str(pdf_prep_man_data["nr_tasks"])
            records = man_pdf_prep(pdf_prep_man_operation, records, item, stat)

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
