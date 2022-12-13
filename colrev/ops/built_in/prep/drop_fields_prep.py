#! /usr/bin/env python
"""Dropping fields as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class DropFieldsPrep(JsonSchemaMixin):
    """Prepares records by dropping fields that are not needed"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = True
    local_index: colrev.env.local_index.LocalIndex

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.local_index = prep_operation.review_manager.get_local_index()

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record by dropping fields that are not required"""

        for key in list(record.data.keys()):
            if key not in prep_operation.fields_to_keep:
                record.remove_field(key=key)
                prep_operation.review_manager.report_logger.info(f"Dropped {key} field")

            elif record.data[key] in ["", "NA"]:
                record.remove_field(key=key)

        if record.data.get("publisher", "") in ["researchgate.net"]:
            record.remove_field(key="publisher")

        return record


if __name__ == "__main__":
    pass
