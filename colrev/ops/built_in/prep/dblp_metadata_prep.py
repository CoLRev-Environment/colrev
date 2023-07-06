#! /usr/bin/env python
"""Consolidation of metadata based on DBLP API as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.dblp as dblp_connector
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class DBLPMetadataPrep(JsonSchemaMixin):
    """Prepares records based on dblp.org metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = (
        "send and email to dblp@dagstuhl.de"
        + " (see https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html)"
    )
    always_apply_changes = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.dblp_source = dblp_connector.DBLPSearchSource(
            source_operation=prep_operation
        )

        self.dblp_prefixes = [
            s.get_origin_prefix()
            for s in prep_operation.review_manager.settings.sources
            if s.endpoint == "colrev.dblp"
        ]

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of the Crossref API"""
        self.dblp_source.check_availability(source_operation=source_operation)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare a record by retrieving its metadata from DBLP"""

        if any(
            dblp_prefix in o
            for dblp_prefix in self.dblp_prefixes
            for o in record.data["colrev_origin"]
        ):
            # Already linked to a dblp record
            return record

        self.dblp_source.get_masterdata(prep_operation=prep_operation, record=record)

        return record
