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
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
    ) -> None:
        """Update the CoLRev curation"""

        for record_dict in records.values():
            if record_dict["colrev_status"] == colrev.record.RecordState.md_imported:
                continue
            if record_dict.get("year", "UNKNOWN") == "UNKNOWN":
                record_dict[
                    "colrev_status"
                ] = colrev.record.RecordState.md_needs_manual_preparation
                colrev.record.Record(data=record_dict).add_masterdata_provenance(
                    key="year",
                    source="colrev_curation.masterdata_restrictions",
                    note="missing",
                )
                continue

            applicable_restrictions = (
                data_operation.review_manager.dataset.get_applicable_restrictions(
                    record_dict=record_dict,
                )
            )

            colrev.record.Record(data=record_dict).apply_restrictions(
                restrictions=applicable_restrictions
            )

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
