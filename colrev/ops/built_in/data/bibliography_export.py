#! /usr/bin/env python
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageInterface)
class BibliographyExport:
    """Export the sample references in Endpoint format"""

    # TODO: this should become a more general endpoint
    # that exports a bibliography (Endnote/Citavi,...)
    # It should have the modes incremental/replace

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

        data_operation.review_manager.get_zotero_translation_service(
            startup_without_waiting=True
        )

    def get_default_setup(self) -> dict:
        endnote_endpoint_details = {
            "endpoint": "ENDNOTE",
            "endnote_data_endpoint_version": "0.1",
            "config": {
                "path": "data/endnote",
            },
        }
        return endnote_endpoint_details

    def __zotero_conversion(self, *, data_operation, content: str) -> bytes:

        zotero_translation_service = (
            data_operation.review_manager.get_zotero_translation_service()
        )
        zotero_translation_service.start_zotero_translators()

        headers = {"Content-type": "text/plain"}
        ret = requests.post(
            "http://127.0.0.1:1969/import",
            headers=headers,
            files={"file": str.encode(content)},
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
            )

        except Exception as exc:
            raise colrev_exceptions.ImportException(
                f"Zotero translators failed ({exc})"
            )

        return export.content

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
    ) -> None:

        endpoint_path = Path("data/endnote")
        endpoint_path.mkdir(exist_ok=True, parents=True)

        if not any(Path(endpoint_path).iterdir()):
            data_operation.review_manager.logger.info("Export all")
            export_filepath = endpoint_path / Path("export_part1.enl")

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

        else:

            enl_files = endpoint_path.glob("*.enl")
            file_numbers = []
            exported_ids = []
            for enl_file_path in enl_files:
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
                export_filepath = endpoint_path / Path(
                    f"export_part{next_file_number}.enl"
                )
                print(export_filepath)
                with open(export_filepath, "w", encoding="utf-8") as file:
                    file.write(enl_data.decode("utf-8"))
                data_operation.review_manager.dataset.add_changes(path=export_filepath)

            else:
                data_operation.review_manager.logger.info(
                    "No additional records to export"
                )

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_id][endpoint_identifier] = True


if __name__ == "__main__":
    pass
