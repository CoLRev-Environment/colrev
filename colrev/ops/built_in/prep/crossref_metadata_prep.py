#! /usr/bin/env python
"""Consolidation of metadata based on Crossref API as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.crossref as crossref_connector
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
class CrossrefMetadataPrep(JsonSchemaMixin):
    """Prepares records based on crossref.org metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.crossref_source = crossref_connector.CrossrefSearchSource(
            source_operation=prep_operation
        )

        self.crossref_prefixes = [
            s.get_origin_prefix()
            for s in prep_operation.review_manager.settings.sources
            if s.endpoint == "colrev.crossref"
        ]

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of the Crossref API"""
        self.crossref_source.check_availability(source_operation=source_operation)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare a record based on Crossref metadata"""

        if any(
            crossref_prefix in o
            for crossref_prefix in self.crossref_prefixes
            for o in record.data["colrev_origin"]
        ):
            # Already linked to a crossref record
            return record

        self.crossref_source.get_masterdata(
            prep_operation=prep_operation, record=record
        )
        return record


if __name__ == "__main__":
    pass
