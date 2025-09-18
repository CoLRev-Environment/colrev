#!/usr/bin/env python3
"""Template for a custom Prep PackageEndpoint"""
from __future__ import annotations

import typing

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
from colrev.constants import Fields


# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


class CustomPrep(base_classes.PrepPackageBaseClass):
    """Class for custom prep scripts"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class(**settings)

    def prepare(
        self,
        record: colrev.record.record.Record,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Update record (metadata)"""

        if Fields.JOURNAL in record.data:
            if record.data[Fields.JOURNAL] == "MISQ":
                record.update_field(
                    key=Fields.JOURNAL, value="MIS Quarterly", source="custom_prep"
                )

        return record
