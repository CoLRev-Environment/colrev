#! /usr/bin/env python
"""Removal of nicknames as a prep operation"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class RemoveNicknamesPrep(JsonSchemaMixin):
    """Prepares records by removing author nicknames"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False

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
        """Prepare the record by removing nicknames from the author field"""

        if "author" in record.data:
            # Replace nicknames in parentheses
            record.data["author"] = re.sub(r"\([^)]*\)", "", record.data["author"])
            record.data["author"] = record.data["author"].replace("  ", " ")
        return record


if __name__ == "__main__":
    pass
