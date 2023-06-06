#! /usr/bin/env python
"""Consolidation of metadata based on OpenAlex API as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.open_alex as open_alex_connector
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class OpenAlexMetadataPrep(JsonSchemaMixin):
    """Prepares records based on OpenAlex metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "TBD"
    always_apply_changes = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.open_alex_source = open_alex_connector.OpenAlexSearchSource(
            source_operation=prep_operation
        )

        self.open_alex_prefixes = [
            s.get_origin_prefix()
            for s in prep_operation.review_manager.settings.sources
            if s.endpoint == "colrev.open_alex"
        ]

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of the OpenAlex API"""
        self.open_alex_source.check_availability(source_operation=source_operation)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare a record based on OpenAlex metadata"""

        if any(
            crossref_prefix in o
            for crossref_prefix in self.open_alex_prefixes
            for o in record.data["colrev_origin"]
        ):
            # Already linked to an OpenAlex record
            return record

        self.open_alex_source.get_masterdata(
            prep_operation=prep_operation, record=record
        )
        return record
