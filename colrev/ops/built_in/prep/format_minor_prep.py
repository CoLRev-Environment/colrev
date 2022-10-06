#! /usr/bin/env python
"""Minor formatting as a prep operation"""
from __future__ import annotations

import re
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


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class FormatMinorPrep(JsonSchemaMixin):
    """Prepares records by applying minor formatting changes"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False
    HTML_CLEANER = re.compile("<.*?>")

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare the record by applying minor formatting changes"""

        for field in list(record.data.keys()):
            # Note : some dois (and their provenance) contain html entities
            if field in [
                "colrev_masterdata_provenance",
                "colrev_data_provenance",
                "doi",
            ]:
                continue
            if field in ["author", "title", "journal"]:
                record.data[field] = re.sub(r"\s+", " ", record.data[field])
                record.data[field] = re.sub(self.HTML_CLEANER, "", record.data[field])

        if record.data.get("volume", "") == "ahead-of-print":
            record.remove_field(key="volume")
        if record.data.get("number", "") == "ahead-of-print":
            record.remove_field(key="number")

        return record


if __name__ == "__main__":
    pass
