#! /usr/bin/env python
from pathlib import Path

import zope.interface
from dacite import from_dict
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter

import colrev_core.process
import colrev_core.record


@zope.interface.implementer(colrev_core.process.PreparationManualEndpoint)
class CoLRevCLIManPrep:
    def __init__(self, *, PREP_MAN, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def prepare_manual(self, PREP_MAN, records):

        # saved_args = locals()

        md_prep_man_data = PREP_MAN.get_data()
        stat_len = md_prep_man_data["nr_tasks"]

        if 0 == stat_len:
            PREP_MAN.REVIEW_MANAGER.logger.info("No records to prepare manually")

        print("Man-prep is not fully implemented (yet).\n")
        print(
            "Edit the records.bib directly, set the colrev_status to 'md_prepared' and "
            "create a commit.\n"  # call this script again to create a commit
        )

        # if PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
        #     if "y" == input("Create commit (y/n)?"):
        #         PREP_MAN.REVIEW_MANAGER.create_commit(
        #            msg= "Manual preparation of records",
        #             manual_author=True,
        #             saved_args=saved_args,
        #         )
        #     else:
        #         input("Press Enter to exit.")
        # else:
        #     input("Press Enter to exit.")

        return records


@zope.interface.implementer(colrev_core.process.PreparationManualEndpoint)
class ExportManPrep:
    def __init__(self, *, PREP_MAN, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def prepare_manual(self, PREP_MAN, records):

        prep_man_path = PREP_MAN.REVIEW_MANAGER.path / Path("prep_man")
        prep_man_path.mkdir(exist_ok=True)

        export_path = prep_man_path / Path("records_prep_man.bib")

        def copy_files_for_man_prep(records):

            prep_man_path_pdfs = prep_man_path / Path("pdfs")
            prep_man_path_pdfs.mkdir(exist_ok=True)
            # TODO : empty prep_man_path_pdfs

            for record in records.values():
                if "file" in record:
                    pdfReader = PdfFileReader(record["file"], strict=False)
                    if pdfReader.getNumPages() >= 1:

                        writer = PdfFileWriter()
                        writer.addPage(pdfReader.getPage(0))
                        target_path = prep_man_path / Path(record["file"])
                        target_path.parents[0].mkdir(exist_ok=True, parents=True)
                        with open(target_path, "wb") as outfile:
                            writer.write(outfile)

        if not export_path.is_file():
            PREP_MAN.REVIEW_MANAGER.logger.info(
                f"Export records for man-prep to {export_path}"
            )

            man_prep_recs = {
                k: v
                for k, v in records.items()
                if colrev_core.record.RecordState.md_needs_manual_preparation
                == v["colrev_status"]
            }
            PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict_to_file(
                records=man_prep_recs, save_path=export_path
            )
            if any("file" in r for r in man_prep_recs.values()):
                copy_files_for_man_prep(records=man_prep_recs)

        else:
            if "y" == input(f"Import changes from {export_path} [y,n]?"):

                PREP_MAN.REVIEW_MANAGER.logger.info(
                    f"Load import changes from {export_path}"
                )

                with open(export_path, encoding="utf8") as target_bib:
                    man_prep_recs = (
                        PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                            load_str=target_bib.read()
                        )
                    )

                records = PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
                for ID, record in man_prep_recs.items():
                    RECORD = colrev_core.record.PrepRecord(data=record)
                    RECORD.update_masterdata_provenance(
                        UNPREPARED_RECORD=RECORD.copy(),
                        REVIEW_MANAGER=PREP_MAN.REVIEW_MANAGER,
                    )
                    RECORD.set_status(
                        target_state=colrev_core.record.RecordState.md_prepared
                    )
                    for k in list(RECORD.data.keys()):
                        if k in ["colrev_status"]:
                            continue
                        if k in records[ID]:
                            if RECORD.data[k] != records[ID][k]:
                                if k in RECORD.data.get(
                                    "colrev_masterdata_provenance", {}
                                ):
                                    RECORD.add_masterdata_provenance(
                                        key=k, source="man_prep"
                                    )
                                else:
                                    RECORD.add_data_provenance(key=k, source="man_prep")

                    records[ID] = RECORD.get_data()

                PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(
                    records=records
                )
                PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
                PREP_MAN.REVIEW_MANAGER.create_commit(msg="Prep-man (ExportManPrep)")

                PREP_MAN.REVIEW_MANAGER.REVIEW_DATASET.set_IDs()
                PREP_MAN.REVIEW_MANAGER.create_commit(
                    msg="Set IDs", script_call="colrev prep", saved_args={}
                )

        return records


@zope.interface.implementer(colrev_core.process.PreparationManualEndpoint)
class CurationJupyterNotebookManPrep:
    def __init__(self, *, PREP_MAN, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

        Path("prep_man").mkdir(exist_ok=True)
        if not Path("prep_man/prep_man_curation.ipynb").is_file():
            PREP_MAN.REVIEW_MANAGER.logger.info(
                f"Activated jupyter notebook to"
                f"{Path('prep_man/prep_man_curation.ipynb')}"
            )
            PREP_MAN.REVIEW_MANAGER.retrieve_package_file(
                template_file=Path("../template/prep_man_curation.ipynb"),
                target=Path("prep_man/prep_man_curation.ipynb"),
            )

    def prepare_manual(self, PREP_MAN, records):

        input(
            "Navigate to the jupyter notebook available at\n"
            "prep_man/prep_man_curation.ipynb\n"
            "Press Enter to continue."
        )
        return records
