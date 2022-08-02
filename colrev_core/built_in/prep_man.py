#! /usr/bin/env python
from pathlib import Path

import zope.interface
from dacite import from_dict

from colrev_core.process import DefaultSettings
from colrev_core.process import PreparationManualEndpoint


@zope.interface.implementer(PreparationManualEndpoint)
class CoLRevCLIManPrep:
    def __init__(self, *, PREP_MAN, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def prepare_manual(self, PREP_MAN, records):

        from colrev.cli import prep_man_records_cli

        records = prep_man_records_cli(PREP_MAN, records)

        return records


@zope.interface.implementer(PreparationManualEndpoint)
class ExportManPrep:
    def __init__(self, *, PREP_MAN, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def prepare_manual(self, PREP_MAN, records):
        from colrev_core.record import RecordState, PrepRecord

        prep_man_path = PREP_MAN.REVIEW_MANAGER.path / Path("prep_man")
        prep_man_path.mkdir(exist_ok=True)

        export_path = prep_man_path / Path("records_prep_man.bib")

        def copy_files_for_man_prep(records):
            from PyPDF2 import PdfFileReader
            from PyPDF2 import PdfFileWriter

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
            return

        if not export_path.is_file():
            PREP_MAN.REVIEW_MANAGER.logger.info(
                f"Export records for man-prep to {export_path}"
            )

            man_prep_recs = {
                k: v
                for k, v in records.items()
                if RecordState.md_needs_manual_preparation == v["colrev_status"]
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
                    RECORD = PrepRecord(data=record)
                    RECORD.update_masterdata_provenance(
                        UNPREPARED_RECORD=RECORD.copy(),
                        REVIEW_MANAGER=PREP_MAN.REVIEW_MANAGER,
                    )
                    RECORD.set_status(target_state=RecordState.md_prepared)
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


@zope.interface.implementer(PreparationManualEndpoint)
class CurationJupyterNotebookManPrep:
    def __init__(self, *, PREP_MAN, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

        Path("prep_man").mkdir(exist_ok=True)
        if not Path("prep_man/prep_man_curation.ipynb").is_file():
            PREP_MAN.REVIEW_MANAGER.logger.info(
                f"Activated jupyter notebook to"
                f"{Path('prep_man/prep_man_curation.ipynb')}"
            )
            self.__retrieve_package_file(
                template_file=Path("../template/prep_man_curation.ipynb"),
                target=Path("prep_man/prep_man_curation.ipynb"),
            )

    def __retrieve_package_file(self, *, template_file: Path, target: Path) -> None:
        import pkgutil

        filedata = pkgutil.get_data(__name__, str(template_file))
        if filedata:
            with open(target, "w", encoding="utf8") as file:
                file.write(filedata.decode("utf-8"))
        return

    def prepare_manual(self, PREP_MAN, records):

        input(
            "Navigate to the jupyter notebook available at\n"
            "prep_man/prep_man_curation.ipynb\n"
            "Press Enter to continue."
        )
        return records
