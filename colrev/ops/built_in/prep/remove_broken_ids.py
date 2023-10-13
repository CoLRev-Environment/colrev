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
from colrev.constants import Fields

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

        if Fields.DOI in record.data:
            if Fields.DOI in record.data.get(Fields.MD_PROV, {}):
                if "doi-not-matching-pattern" in record.data[Fields.MD_PROV][
                    Fields.DOI
                ]["note"].split(","):
                    record.remove_field(key=Fields.DOI)

        if Fields.ISBN in record.data:
            if Fields.ISBN in record.data.get(Fields.MD_PROV, {}):
                if "isbn-not-matching-pattern" in record.data[Fields.MD_PROV][
                    Fields.ISBN
                ]["note"].split(","):
                    record.remove_field(key=Fields.ISBN)

        return record
