#! /usr/bin/env python
"""Removal of broken IDs as a prep operation"""
from __future__ import annotations

import logging
import typing

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import DefectCodes
from colrev.constants import Fields


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class RemoveBrokenIDPrep(base_classes.PrepPackageBaseClass):
    """Prepares records by removing invalid IDs DOIs/ISBNs"""

    ci_supported: bool = Field(default=True)

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    # check_status: relies on crossref / openlibrary connectors!
    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = colrev.package_manager.package_settings.DefaultSettings(
            **settings
        )
        self.prep_operation = prep_operation
        self.review_manager = prep_operation.review_manager

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare the record by removing broken IDs (invalid DOIs/ISBNs)"""

        if self.prep_operation.polish and not self.review_manager.force_mode:
            return record

        if DefectCodes.DOI_NOT_MATCHING_PATTERN in record.get_field_provenance_notes(
            Fields.DOI
        ):
            record.remove_field(key=Fields.DOI)

        if DefectCodes.ISBN_NOT_MATCHING_PATTERN in record.get_field_provenance_notes(
            Fields.ISBN
        ):
            record.remove_field(key=Fields.ISBN)

        return record
