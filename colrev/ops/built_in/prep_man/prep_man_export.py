#! /usr/bin/env python
"""Export of bib/pdfs as a prep-man operation"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter

import colrev.env.package_manager
import colrev.env.utils
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.prep_man

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepManPackageEndpointInterface)
@dataclass
class ExportManPrep(JsonSchemaMixin):
    """Manual preparation based on exported and imported metadata (and PDFs if any)"""

    @dataclass
    class ExportManPrepSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for ExportManPrep"""

        endpoint: str
        pdf_handling_mode: str = "symlink"

        _details = {
            "pdf_handling_mode": {
                "tooltip": "Indicates how linked PDFs are handled (symlink/copy_first_page)"
            },
        }

    settings_class = ExportManPrepSettings

    def __init__(
        self,
        *,
        prep_man_operation: colrev.ops.prep_man.PrepMan,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:

        if "pdf_handling_mode" not in settings:
            settings["pdf_handling_mode"] = "symlink"
        assert settings["pdf_handling_mode"] in ["symlink", "copy_first_page"]

        self.settings = self.settings_class.load_settings(data=settings)

        self.prep_man_path = prep_man_operation.review_manager.path / Path("prep_man")
        self.prep_man_path.mkdir(exist_ok=True)
        self.export_path = self.prep_man_path / Path("records_prep_man.bib")

    def __copy_files_for_man_prep(self, *, records: dict) -> None:

        prep_man_path_pdfs = self.prep_man_path / Path("data/pdfs")
        if prep_man_path_pdfs.is_dir():
            input(f"Remove {prep_man_path_pdfs} and press Enter.")
        prep_man_path_pdfs.mkdir(exist_ok=True, parents=True)

        for record in records.values():
            if "file" in record:
                target_path = self.prep_man_path / Path(record["file"])
                target_path.parents[0].mkdir(exist_ok=True, parents=True)

                if "symlink" == self.settings.pdf_handling_mode:
                    target_path.symlink_to(Path(record["file"]).resolve())

                if "copy_first_page" == self.settings.pdf_handling_mode:
                    pdf_reader = PdfFileReader(str(record["file"]), strict=False)
                    if len(pdf_reader.pages) >= 1:

                        writer = PdfFileWriter()
                        writer.addPage(pdf_reader.getPage(0))
                        with open(target_path, "wb") as outfile:
                            writer.write(outfile)

    def __export_prep_man(
        self,
        *,
        prep_man_operation: colrev.ops.prep_man.PrepMan,
        records: typing.Dict[str, typing.Dict],
    ) -> None:
        prep_man_operation.review_manager.logger.info(
            f"Export records for man-prep to {self.export_path}"
        )

        man_prep_recs = {
            k: v
            for k, v in records.items()
            if colrev.record.RecordState.md_needs_manual_preparation
            == v["colrev_status"]
        }
        prep_man_operation.review_manager.dataset.save_records_dict_to_file(
            records=man_prep_recs, save_path=self.export_path
        )
        if any("file" in r for r in man_prep_recs.values()):
            self.__copy_files_for_man_prep(records=man_prep_recs)

    def __import_prep_man(
        self, *, prep_man_operation: colrev.ops.prep_man.PrepMan
    ) -> None:

        # pylint: disable=too-many-branches
        prep_man_operation.review_manager.logger.info(
            "Load import changes from "
            f"{self.export_path.relative_to(prep_man_operation.review_manager.path)}"
        )

        with open(self.export_path, encoding="utf8") as target_bib:
            man_prep_recs = prep_man_operation.review_manager.dataset.load_records_dict(
                load_str=target_bib.read()
            )

        imported_records = []
        records = prep_man_operation.review_manager.dataset.load_records_dict()
        for record_id, record_dict in man_prep_recs.items():
            if record_id not in records:
                print(f"ID no longer in records: {record_id}")
                continue
            record = colrev.record.PrepRecord(data=record_dict)
            record.update_masterdata_provenance()
            record.set_status(target_state=colrev.record.RecordState.md_prepared)
            if colrev.record.RecordState.md_prepared == record.data["colrev_status"]:
                imported_records.append(record.data["ID"])
            for k in list(record.data.keys()):
                if k in [
                    "colrev_status",
                    "colrev_masterdata_provenance",
                    "colrev_data_provenance",
                    "colrev_id",
                ]:
                    continue
                if k in records[record_id]:
                    if record.data[k] != records[record_id][k]:
                        if k in record.data.get("colrev_masterdata_provenance", {}):
                            record.add_masterdata_provenance(key=k, source="man_prep")
                        else:
                            record.add_data_provenance(key=k, source="man_prep")
                else:
                    if k in records[record_id]:
                        del records[record_id][k]
                    if k in record.data.get("colrev_masterdata_provenance", {}):
                        record.add_masterdata_provenance(
                            key=k, source="man_prep", note="not_missing"
                        )
                    else:
                        record.add_data_provenance(
                            key=k, source="man_prep", note="not_missing"
                        )
            records[record_id] = record.get_data()

        prep_man_operation.review_manager.dataset.save_records_dict(records=records)
        prep_man_operation.review_manager.dataset.add_record_changes()
        prep_man_operation.review_manager.create_commit(msg="Prep-man (ExportManPrep)")

        prep_man_operation.review_manager.dataset.set_ids(selected_ids=imported_records)
        prep_man_operation.review_manager.create_commit(msg="Set IDs")

    def prepare_manual(
        self, prep_man_operation: colrev.ops.prep_man.PrepMan, records: dict
    ) -> dict:
        """Prepare records manually by extracting the subset of records to a separate BiBTex file"""

        if not self.export_path.is_file():
            self.__export_prep_man(
                prep_man_operation=prep_man_operation, records=records
            )
        else:
            if "y" == input(
                "Import changes from "
                f"{self.export_path.relative_to(prep_man_operation.review_manager.path)} [y,n]?"
            ):
                self.__import_prep_man(prep_man_operation=prep_man_operation)

        return records


if __name__ == "__main__":
    pass
