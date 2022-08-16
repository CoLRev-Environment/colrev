#! /usr/bin/env python
import pprint
import typing
from pathlib import Path

import zope.interface
from dacite import from_dict

import colrev.process
import colrev.record


@zope.interface.implementer(colrev.process.PDFPreparationManualEndpoint)
class CoLRevCLIPDFManPrep:
    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def prep_man_pdf(self, PDF_PREP_MAN, records):

        pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

        def man_pdf_prep(PDF_PREP_MAN, records: typing.Dict, item, stat) -> typing.Dict:

            PDF_PREP_MAN.REVIEW_MANAGER.logger.debug(
                f"called man_pdf_prep for {pp.pformat(item)}"
            )
            print(stat)
            pp.pprint(item)

            record = records[item["ID"]]
            if (
                colrev.record.RecordState.pdf_needs_manual_preparation
                != record["colrev_status"]
            ):
                return record

            print(
                "Manual preparation needed:"
                f" {record.get('pdf_prep_hints', 'Details not available.')}"
            )

            filepath = (
                PDF_PREP_MAN.REVIEW_MANAGER.paths["PDF_DIRECTORY"]
                / f"{record['ID']}.pdf"
            )
            pdf_path = PDF_PREP_MAN.REVIEW_MANAGER.path / Path(record["file"])
            if pdf_path.is_file() or filepath.is_file():
                if "y" == input("Prepared? (y/n)?"):
                    RECORD = colrev.record.Record(data=record)
                    RECORD.pdf_man_prep(REVIEW_MANAGER=PDF_PREP_MAN.REVIEW_MANAGER)

            else:
                print(f'File does not exist ({record["ID"]})')

            return records

        saved_args = locals()

        pdf_prep_man_data = PDF_PREP_MAN.get_data()
        records = PDF_PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for i, item in enumerate(pdf_prep_man_data["items"]):
            stat = str(i + 1) + "/" + str(pdf_prep_man_data["nr_tasks"])
            records = man_pdf_prep(PDF_PREP_MAN, records, item, stat)

        PDF_PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        PDF_PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        if PDF_PREP_MAN.pdfs_prepared_manually():
            if "y" == input("Create commit (y/n)?"):

                PDF_PREP_MAN.REVIEW_MANAGER.create_commit(
                    msg="Prepare PDFs manually",
                    manual_author=True,
                    saved_args=saved_args,
                )
        else:
            PDF_PREP_MAN.REVIEW_MANAGER.logger.info(
                "Prepare PDFs manually. Afterwards, use colrev pdf-get-man"
            )

        return records
