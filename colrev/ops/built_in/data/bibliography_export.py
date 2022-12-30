#! /usr/bin/env python
"""Export of references in different bibliographical formats as a data operation"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.data


@dataclass
class BibFormats(Enum):
    """Enum of available bibliography formats"""

    # pylint: disable=invalid-name
    endnote = "endnote"


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class BibliographyExport(JsonSchemaMixin):
    """Export the sample references in Endpoint format"""

    # gh_issue https://github.com/geritwagner/colrev/issues/70
    # this should become a more general endpoint
    # that exports a bibliography (Endnote/Citavi,...)
    # It should have the modes incremental/replace

    @dataclass
    class BibliographyExportSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for BibliographyExport"""

        endpoint: str
        version: str
        bib_format: BibFormats
        endpoint_dir = Path("endnote")

    settings_class = BibliographyExportSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        if "endpoint_dir" not in settings:
            settings["endpoint_dir"] = "endnote"
        if "bib_format" not in settings:
            settings["bib_format"] = "endnote"

        self.settings = self.settings_class.load_settings(data=settings)

        data_operation.review_manager.get_zotero_translation_service()

        self.endpoint_path = (
            data_operation.review_manager.output_dir / self.settings.endpoint_dir
        )

    # gh_issue https://github.com/geritwagner/colrev/issues/70
    # change to DefaultSettings structure...
    def get_default_setup(self) -> dict:
        """Get the default setup"""
        endnote_endpoint_details = {
            "endpoint": "colrev_built_in.bibliography_export",
            "endnote_data_endpoint_version": "0.1",
            "config": {
                "path": "endnote",
            },
        }
        return endnote_endpoint_details

    def __zotero_conversion(
        self, *, data_operation: colrev.ops.data.Data, content: str
    ) -> bytes:

        zotero_translation_service = (
            data_operation.review_manager.get_zotero_translation_service()
        )
        zotero_translation_service.start_zotero_translators()

        headers = {"Content-type": "text/plain"}
        ret = requests.post(
            "http://127.0.0.1:1969/import",
            headers=headers,
            files={"file": str.encode(content)},
            timeout=30,
        )
        headers = {"Content-type": "application/json"}
        if "No suitable translators found" == ret.content.decode("utf-8"):
            raise colrev_exceptions.ImportException(
                "Zotero translators: No suitable translators found"
            )

        try:
            zotero_format = json.loads(ret.content)
            export = requests.post(
                "http://127.0.0.1:1969/export?format=refer",
                headers=headers,
                json=zotero_format,
                timeout=30,
            )

        except Exception as exc:
            raise colrev_exceptions.ImportException(
                f"Zotero translators failed ({exc})"
            )

        return export.content

    def __export_bibliography_full(
        self, *, data_operation: colrev.ops.data.Data, records: dict
    ) -> None:
        data_operation.review_manager.logger.info("Export all")
        export_filepath = self.endpoint_path / Path("export_part1.enl")

        selected_records = {
            ID: r
            for ID, r in records.items()
            if r["colrev_status"]
            in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]
        }

        content = data_operation.review_manager.dataset.parse_bibtex_str(
            recs_dict_in=selected_records
        )

        enl_data = self.__zotero_conversion(
            data_operation=data_operation, content=content
        )

        with open(export_filepath, "w", encoding="utf-8") as export_file:
            export_file.write(enl_data.decode("utf-8"))
        data_operation.review_manager.dataset.add_changes(path=export_filepath)

    def __export_bibliography_incremental(
        self, *, data_operation: colrev.ops.data.Data, records: dict
    ) -> None:

        file_numbers, exported_ids = [], []
        for enl_file_path in self.endpoint_path.glob("*.enl"):
            file_numbers.append(int(re.findall(r"\d+", str(enl_file_path.name))[0]))
            with open(enl_file_path, encoding="utf-8") as enl_file:
                for line in enl_file:
                    if "%F" == line[:2]:
                        record_id = line[3:].lstrip().rstrip()
                        exported_ids.append(record_id)

        data_operation.review_manager.logger.info(
            "IDs that have already been exported (in the other export files):"
            f" {exported_ids}"
        )

        selected_records = {
            ID: r
            for ID, r in records.items()
            if r["colrev_status"]
            in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]
        }

        if len(selected_records) > 0:

            content = data_operation.review_manager.dataset.parse_bibtex_str(
                recs_dict_in=selected_records
            )

            enl_data = self.__zotero_conversion(
                data_operation=data_operation, content=content
            )

            next_file_number = str(max(file_numbers) + 1)
            export_filepath = self.endpoint_path / Path(
                f"export_part{next_file_number}.enl"
            )
            print(export_filepath)
            with open(export_filepath, "w", encoding="utf-8") as file:
                file.write(enl_data.decode("utf-8"))
            data_operation.review_manager.dataset.add_changes(path=export_filepath)

        else:
            data_operation.review_manager.logger.info("No additional records to export")

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
        silent_mode: bool,  # pylint: disable=unused-argument
    ) -> None:
        """Update the data/bibliography"""

        self.endpoint_path.mkdir(exist_ok=True, parents=True)

        if not any(Path(self.endpoint_path).iterdir()):
            self.__export_bibliography_full(
                data_operation=data_operation, records=records
            )

        else:
            self.__export_bibliography_incremental(
                data_operation=data_operation, records=records
            )

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status_matrix"""
        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_id][endpoint_identifier] = True

    def get_advice(
        self,
        review_manager: colrev.review_manager.ReviewManager,  # pylint: disable=unused-argument
    ) -> dict:
        """Get advice on the next steps (for display in the colrev status)"""

        advice = {
            "msg": f"The references are updated in the {self.endpoint_path}",
            "detailed_msg": "TODO",
        }
        return advice


if __name__ == "__main__":
    pass
