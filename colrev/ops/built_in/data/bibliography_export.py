#! /usr/bin/env python
"""Export of references in different bibliographical formats as a data operation"""
from __future__ import annotations

import json
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
    zotero = "zotero"
    jabref = "jabref"
    mendeley = "mendeley"
    citavi = "citavi"
    rdf_bibliontology = "rdf_bibliontology"


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class BibliographyExport(JsonSchemaMixin):
    """Export the sample references in Endpoint format"""

    ZOTERO_FORMATS = [BibFormats.endnote, BibFormats.mendeley]

    @dataclass
    class BibliographyExportSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for BibliographyExport"""

        endpoint: str
        version: str
        incremental: bool
        bib_format: BibFormats

    settings_class = BibliographyExportSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:

        if "bib_format" not in settings:
            settings["bib_format"] = "endnote"
        settings["bib_format"] = BibFormats[settings["bib_format"]]
        if "incremental" not in settings:
            settings["incremental"] = False
        if "version" not in settings:
            settings["version"] = "0.1"

        self.settings = self.settings_class.load_settings(data=settings)

        data_operation.review_manager.get_zotero_translation_service()

        # TODO : update the following:
        self.endpoint_path = data_operation.review_manager.output_dir / Path("endnote")

    # gh_issue https://github.com/geritwagner/colrev/issues/70
    # change to DefaultSettings structure...
    def get_default_setup(self) -> dict:
        """Get the default setup"""
        endnote_endpoint_details = {
            "endpoint": "colrev_built_in.bibliography_export",
            "version": "0.1",
            "bib_format": "endnote",
        }
        return endnote_endpoint_details

    def __zotero_conversion(
        self, *, data_operation: colrev.ops.data.Data, selected_records: list
    ) -> None:

        # TODO : check if file already available / incremental

        # Strange: comparing BibFormats.endnote to self.settings.bib_format
        # does not work...
        # https://github.com/zotero/translation-server/blob/master/src/formats.js
        if "endnote" == self.settings.bib_format.name:
            export_filepath = self.endpoint_path / Path("export_part.enl")
            selected_format = "refer"

        elif "zotero" == self.settings.bib_format.name:
            export_filepath = self.endpoint_path / Path("zotero.bib")
            # TODO : IDs are not preserved when using bilatex conversion through zotero
            selected_format = "biblatex"

        elif "jabref" == self.settings.bib_format.name:
            export_filepath = self.endpoint_path / Path("jabref.bib")
            selected_format = "biblatex"

        elif "mendeley" == self.settings.bib_format.name:
            export_filepath = self.endpoint_path / Path("mendeley.ris")
            selected_format = "ris"

        else:
            data_operation.review_manager.logger.info(
                f"Format {self.settings.bib_format} not supported."
            )
            return

        content = data_operation.review_manager.dataset.parse_bibtex_str(
            recs_dict_in=selected_records
        )

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
            json_content = json.loads(ret.content)
            export = requests.post(
                f"http://127.0.0.1:1969/export?format={selected_format}",
                headers=headers,
                json=json_content,
                timeout=30,
            )
            with open(export_filepath, "w", encoding="utf-8") as export_file:
                export_file.write(export.content.decode("utf-8"))
            data_operation.review_manager.dataset.add_changes(path=export_filepath)

        except Exception as exc:
            raise colrev_exceptions.ImportException(
                f"Zotero translators failed ({exc})"
            )

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
        silent_mode: bool,  # pylint: disable=unused-argument
    ) -> None:
        """Update the data/bibliography"""

        self.endpoint_path.mkdir(exist_ok=True, parents=True)

        data_operation.review_manager.logger.info("Export all")

        selected_records = {
            ID: r
            for ID, r in records.items()
            if r["colrev_status"]
            in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]
        }

        if self.settings.bib_format in self.ZOTERO_FORMATS:
            self.__zotero_conversion(
                data_operation=data_operation, selected_records=selected_records
            )

        else:
            data_operation.review_manager.logger.info(
                f"Not yet implemented ({self.settings.bib_format})"
            )

    # if not any(Path(self.endpoint_path).iterdir()):
    #     self.__export_bibliography_full(
    #         data_operation=data_operation, records=records
    #     )

    # else:
    #     self.__export_bibliography_incremental(
    #         data_operation=data_operation, records=records
    #     )

    # def __export_bibliography_incremental(
    #     self, *, data_operation: colrev.ops.data.Data, records: dict
    # ) -> None:

    #     file_numbers, exported_ids = [], []
    #     for enl_file_path in self.endpoint_path.glob("*.enl"):
    #         file_numbers.append(int(re.findall(r"\d+", str(enl_file_path.name))[0]))
    #         with open(enl_file_path, encoding="utf-8") as enl_file:
    #             for line in enl_file:
    #                 if "%F" == line[:2]:
    #                     record_id = line[3:].lstrip().rstrip()
    #                     exported_ids.append(record_id)

    #     data_operation.review_manager.logger.info(
    #         "IDs that have already been exported (in the other export files):"
    #         f" {exported_ids}"
    #     )

    #     selected_records = {
    #         ID: r
    #         for ID, r in records.items()
    #         if r["colrev_status"]
    #         in [
    #             colrev.record.RecordState.rev_included,
    #             colrev.record.RecordState.rev_synthesized,
    #         ]
    #     }

    #     if len(selected_records) > 0:

    #         enl_data = self.__zotero_conversion(
    #             data_operation=data_operation, selected_records=selected_records
    #         )

    #         next_file_number = str(max(file_numbers) + 1)
    #         export_filepath = self.endpoint_path / Path(
    #             f"export_part{next_file_number}.enl"
    #         )
    #         print(export_filepath)
    #         with open(export_filepath, "w", encoding="utf-8") as file:
    #             file.write(enl_data.decode("utf-8"))
    #         data_operation.review_manager.dataset.add_changes(path=export_filepath)

    #     else:
    #         data_operation.review_manager.logger.info("No additional records to export")

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

        data_endpoint = "Data operation [bibliography export data endpoint]: "

        advice = {
            "msg": f"{data_endpoint}"
            + f"\n    - The references are updated automatically ({self.endpoint_path})",
            "detailed_msg": "TODO",
        }
        return advice


if __name__ == "__main__":
    pass
