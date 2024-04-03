#! /usr/bin/env python
"""Removal of broken IDs as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record.record
from colrev.constants import DefectCodes
from colrev.constants import Fields


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
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.prep_operation = prep_operation
        self.review_manager = prep_operation.review_manager

    def prepare(
        self, record: colrev.record.record_prep.PrepRecord
    ) -> colrev.record.record.Record:
        """Prepare the record by removing broken IDs (invalid DOIs/ISBNs)"""

        if self.prep_operation.polish and not self.review_manager.force_mode:
            return record

        if (
            DefectCodes.DOI_NOT_MATCHING_PATTERN
            in record.get_masterdata_provenance_notes(Fields.DOI)
        ):
            record.remove_field(key=Fields.DOI)

        if (
            DefectCodes.ISBN_NOT_MATCHING_PATTERN
            in record.get_masterdata_provenance_notes(Fields.ISBN)
        ):
            record.remove_field(key=Fields.ISBN)

        return record
