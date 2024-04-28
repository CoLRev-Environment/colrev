#! /usr/bin/env python
"""Exclude collections as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Fields

# pylint: disable=duplicate-code


# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.package_manager.interfaces.PrepInterface)
@dataclass
class ExcludeCollectionsPrep(JsonSchemaMixin):
    """Prepares records by excluding collection entries (e.g., proceedings)"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Prepare records by excluding collections (proceedings)"""

        if record.data[Fields.ENTRYTYPE].lower() == "proceedings":
            record.prescreen_exclude(reason="collection/proceedings")

        return record
