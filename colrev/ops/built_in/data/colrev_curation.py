#! /usr/bin/env python
"""Creation of a markdown manuscript as part of the data operations"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class ColrevCuration(JsonSchemaMixin):
    """CoLRev Curation"""

    @dataclass
    class ColrevCurationSettings(JsonSchemaMixin):
        """Colrev Curation settings"""

        endpoint: str
        version: str
        curation_url: str
        curated_masterdata: bool
        masterdata_restrictions: dict
        curated_fields: list

    settings_class = ColrevCurationSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,
        settings: dict,
    ) -> None:

        # Set default values (if necessary)
        if "version" not in settings:
            settings["version"] = "0.1"

        self.settings = from_dict(
            data_class=self.settings_class,
            data=settings,
        )

        self.data_operation = data_operation

    def get_default_setup(self) -> dict:
        """Get the default setup"""

        curation_endpoint_details = {
            "endpoint": "colrev_built_in.colrev_curation",
            "version": "0.1",
            "curation_url": "TODO",
            "curated_masterdata": True,
            "masterdata_restrictions": {
                1900: {
                    "ENTRYTYPE": "article",
                    "journal": "TODO",
                    "volume": True,
                    "number": True,
                }
            },
            "curated_fields": ["doi", "url"],
        }

        return curation_endpoint_details

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        records: dict,
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
    ) -> None:
        """Update the CoLRev curation"""

        # pylint: disable=too-many-branches
        start_year_values = list(self.settings.masterdata_restrictions.keys())

        for record in records.values():
            if record["colrev_status"] == colrev.record.RecordState.md_imported:
                continue
            if record.get("year", "UNKOWN") == "UNKNOWN":
                record[
                    "colrev_status"
                ] = colrev.record.RecordState.md_needs_manual_preparation
                continue

            year_index_diffs = [int(record["year"]) - int(x) for x in start_year_values]
            year_index_diffs = [x if x > 0 else 2000 for x in year_index_diffs]
            index_min = min(
                range(len(year_index_diffs)), key=year_index_diffs.__getitem__
            )
            applicable_requirements = self.settings.masterdata_restrictions[
                start_year_values[index_min]
            ]
            if "ENTRYTYPE" in applicable_requirements:
                if applicable_requirements["ENTRYTYPE"] != record["ENTRYTYPE"]:
                    record[
                        "colrev_status"
                    ] = colrev.record.RecordState.md_needs_manual_preparation
            if "journal" in applicable_requirements:
                if applicable_requirements["journal"] != record.get("journal", ""):
                    record[
                        "colrev_status"
                    ] = colrev.record.RecordState.md_needs_manual_preparation

            if "booktitle" in applicable_requirements:
                if applicable_requirements["booktitle"] != record.get("booktitle", ""):
                    record[
                        "colrev_status"
                    ] = colrev.record.RecordState.md_needs_manual_preparation

            if "volume" in applicable_requirements:
                if applicable_requirements["volume"]:
                    if "volume" not in record:
                        record[
                            "colrev_status"
                        ] = colrev.record.RecordState.md_needs_manual_preparation

            if "number" in applicable_requirements:
                if applicable_requirements["number"]:
                    if "number" not in record:
                        record[
                            "colrev_status"
                        ] = colrev.record.RecordState.md_needs_manual_preparation

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status_matrix"""

        for item in synthesized_record_status_matrix:
            item[endpoint_identifier] = True


if __name__ == "__main__":
    pass
