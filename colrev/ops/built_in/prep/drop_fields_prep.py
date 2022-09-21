#! /usr/bin/env python
"""Dropping fields as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageInterface)
@dataclass
class DropFieldsPrep(JsonSchemaMixin):
    """Prepares records by dropping fields that are not needed"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False
    local_index: colrev.env.local_index.LocalIndex

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:

        for key in list(record.data.keys()):
            if key not in prep_operation.fields_to_keep:
                record.remove_field(key=key)
                prep_operation.review_manager.report_logger.info(f"Dropped {key} field")

            elif record.data[key] in ["", "NA"]:
                record.remove_field(key=key)

        if record.data.get("publisher", "") in ["researchgate.net"]:
            record.remove_field(key="publisher")

        if "volume" in record.data.keys() and "number" in record.data.keys():
            # Note : cannot use local_index as an attribute of PrepProcess
            # because it creates problems with multiprocessing

            self.local_index = prep_operation.review_manager.get_local_index()

            fields_to_remove = self.local_index.get_fields_to_remove(
                record_dict=record.get_data()
            )
            for field_to_remove in fields_to_remove:
                if field_to_remove in record.data:
                    # TODO : maybe use set_masterdata_complete()?
                    record.remove_field(
                        key=field_to_remove, not_missing_note=True, source="local_index"
                    )

        return record


if __name__ == "__main__":
    pass
