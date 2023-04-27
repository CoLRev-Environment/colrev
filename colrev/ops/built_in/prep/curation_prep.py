#! /usr/bin/env python
"""Preparation of curations"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
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

        applicable_restrictions = (
            prep_operation.review_manager.dataset.get_applicable_restrictions(
                record_dict=record.data,
            )
        )

        colrev.record.Record(data=record.data).apply_restrictions(
            restrictions=applicable_restrictions
        )
        if any(
            "missing" in note
            for note in [
                x["note"]
                for x in record.data.get("colrev_masterdata_provenance", {}).values()
            ]
        ):
            colrev.record.Record(data=record.data).set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )
        return record


if __name__ == "__main__":
    pass
