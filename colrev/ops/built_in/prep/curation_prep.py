#! /usr/bin/env python
"""Preparation of curations"""
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
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class CurationPrep(JsonSchemaMixin):
    """Preparation of curations"""

    settings_class = colrev.env.package_manager.DefaultSettings
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
        self.quality_model = prep_operation.review_manager.get_qm()
        self.prep_operation = prep_operation

    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare records in a CoLRev curation"""

        # pylint: disable=too-many-branches

        if (
            record.data["colrev_status"]
            == colrev.record.RecordState.rev_prescreen_excluded
        ):
            return record

        if record.data.get("year", "UNKNOWN") == "UNKNOWN":
            record.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )
            colrev.record.Record(data=record.data).add_masterdata_provenance(
                key="year",
                source="colrev_curation.masterdata_restrictions",
                note="missing",
            )
            return record

        colrev.record.Record(data=record.data).update_masterdata_provenance(
            qm=self.quality_model
        )

        return record
