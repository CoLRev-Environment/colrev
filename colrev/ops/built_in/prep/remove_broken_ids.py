#! /usr/bin/env python
"""Removal of broken IDs as a prep operation"""
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
class RemoveBrokenIDPrep(JsonSchemaMixin):
    """Prepares records by removing invalid IDs DOIs/ISBNs"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    # check_status: relies on crossref / openlibrary connectors!
    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record by removing broken IDs (invalid DOIs/ISBNs)"""

        if prep_operation.polish and not prep_operation.force_mode:
            return record

        if "doi" in record.data:
            if "doi" in record.data.get("colrev_masterdata_provenance", {}):
                if "doi-not-matching-pattern" in record.data[
                    "colrev_masterdata_provenance"
                ]["doi"]["note"].split(","):
                    record.remove_field(key="doi")

        if "isbn" in record.data:
            if "isbn" in record.data.get("colrev_masterdata_provenance", {}):
                if "isbn-not-matching-pattern" in record.data[
                    "colrev_masterdata_provenance"
                ]["isbn"]["note"].split(","):
                    record.remove_field(key="isbn")

        return record
