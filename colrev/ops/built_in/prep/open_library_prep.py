#! /usr/bin/env python
"""Consolidation of metadata based on OpenLibrary API as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.open_library as open_library_connector
import colrev.ops.search_sources
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class OpenLibraryMetadataPrep(JsonSchemaMixin):
    """Prepares records based on openlibrary.org metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "ask the publisher to correct the metadata"
    always_apply_changes = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.open_library_connector = open_library_connector.OpenLibrarySearchSource(
            source_operation=prep_operation
        )

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of the Crossref API"""
        self.open_library_connector.check_availability(
            source_operation=source_operation
        )

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record metadata based on OpenLibrary"""

        if record.data.get("ENTRYTYPE", "NA") != "book":
            return record

        self.open_library_connector.get_masterdata(
            prep_operation=prep_operation, record=record
        )

        return record


if __name__ == "__main__":
    pass
