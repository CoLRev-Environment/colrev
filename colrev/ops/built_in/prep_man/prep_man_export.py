#! /usr/bin/env python
"""Export of bib/pdfs as a prep-man operation"""
from __future__ import annotations

import os
import subprocess
import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter

import colrev.env.package_manager
import colrev.env.utils
import colrev.record

# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep_man


@zope.interface.implementer(colrev.env.package_manager.PrepManPackageEndpointInterface)
@dataclass
class ExportManPrep(JsonSchemaMixin):
    """Manual preparation based on exported and imported metadata (and PDFs if any)"""

    settings: ExportManPrepSettings
    ci_supported: bool = False

    RELATIVE_PREP_MAN_PATH = Path("records_prep_man.bib")

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

        self.review_manager = prep_man_operation.review_manager

        self.prep_man_bib_path = (
            self.review_manager.prep_dir / self.RELATIVE_PREP_MAN_PATH
        )

        self.review_manager.prep_dir.mkdir(exist_ok=True, parents=True)

    def __copy_files_for_man_prep(self, *, records: dict) -> None:
        prep_man_path_pdfs = self.review_manager.prep_dir / Path("pdfs")
        if prep_man_path_pdfs.is_dir():
            input(f"Remove {prep_man_path_pdfs} and press Enter.")
        prep_man_path_pdfs.mkdir(exist_ok=True, parents=True)

        for record in records.values():
            if "file" in record:
                target_path = self.review_manager.prep_dir / Path(record["file"])
                target_path.parents[0].mkdir(exist_ok=True, parents=True)

                if self.settings.pdf_handling_mode == "symlink":
                    target_path.symlink_to(Path(record["file"]).resolve())

                if self.settings.pdf_handling_mode == "copy_first_page":
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
            f"Export records for man-prep to {self.prep_man_bib_path}"
        )

        man_prep_recs = {
            k: v
            for k, v in records.items()
            if colrev.record.RecordState.md_needs_manual_preparation
            == v["colrev_status"]
        }
        prep_man_operation.review_manager.dataset.save_records_dict_to_file(
            records=man_prep_recs, save_path=self.prep_man_bib_path
        )
        if any("file" in r for r in man_prep_recs.values()):
            self.__copy_files_for_man_prep(records=man_prep_recs)
        if "pytest" not in os.getcwd():
            # os.system('%s %s' % (os.getenv('EDITOR'), self.prep_man_bib_path))
            subprocess.call(["xdg-open", str(self.prep_man_bib_path)])

    def __import_prep_man(
        self, *, prep_man_operation: colrev.ops.prep_man.PrepMan
    ) -> None:
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals

        prep_man_operation.review_manager.logger.info(
            "Load import changes from "
            f"{self.prep_man_bib_path.relative_to(prep_man_operation.review_manager.path)}"
        )

        with open(self.prep_man_bib_path, encoding="utf8") as target_bib:
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
            colrev_data_provenance_keys_to_drop = []
            for key, items in record.data.get("colrev_data_provenance", {}).items():
                if key not in record.data and "not_missing" not in items["note"]:
                    colrev_data_provenance_keys_to_drop.append(key)
            for (
                colrev_data_provenance_key_to_drop
            ) in colrev_data_provenance_keys_to_drop:
                del record.data["colrev_data_provenance"][
                    colrev_data_provenance_key_to_drop
                ]

            colrev_masterdata_provenance_keys_to_drop = []
            for key, items in record.data.get(
                "colrev_masterdata_provenance", {}
            ).items():
                if key not in record.data and "not_missing" not in items["note"]:
                    colrev_masterdata_provenance_keys_to_drop.append(key)
            for (
                colrev_masterdata_provenance_key_to_drop
            ) in colrev_masterdata_provenance_keys_to_drop:
                del record.data["colrev_masterdata_provenance"][
                    colrev_masterdata_provenance_key_to_drop
                ]

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

        if not self.prep_man_bib_path.is_file():
            self.__export_prep_man(
                prep_man_operation=prep_man_operation, records=records
            )
        else:
            selected_path = self.prep_man_bib_path.relative_to(
                prep_man_operation.review_manager.path
            )
            if input(f"Import changes from {selected_path} [y,n]?") == "y":
                self.__import_prep_man(prep_man_operation=prep_man_operation)

        return records


if __name__ == "__main__":
    pass
