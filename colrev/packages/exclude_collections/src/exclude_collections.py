#! /usr/bin/env python
"""Exclude collections as a prep operation"""
from __future__ import annotations

import logging
import typing

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Fields

# pylint: disable=duplicate-code
# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods


class ExcludeCollectionsPrep(base_classes.PrepPackageBaseClass):
    """Prepares records by excluding collection entries (e.g., proceedings)"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=True)

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare records by excluding collections (proceedings)"""

        if record.data[Fields.ENTRYTYPE].lower() == "proceedings":
            record.prescreen_exclude(reason="collection/proceedings")

        return record
