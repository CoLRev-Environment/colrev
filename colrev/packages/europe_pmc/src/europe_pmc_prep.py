#! /usr/bin/env python
"""Consolidation of metadata based on Europe PMC API as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.packages.europe_pmc.src.europe_pmc as europe_pmc_connector
import colrev.record.record


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.PrepInterface)
@dataclass
class EuropePMCMetadataPrep(JsonSchemaMixin):
    """Prepares records based on Europe PCM metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "ask the publisher to correct the metadata"
    always_apply_changes = False
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/search_sources/europe_pmc.md"
    )

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
        """Prepare a record based on Europe PMC metadata"""

        # pylint: disable=invalid-name
        EuropePMCSearchSource = europe_pmc_connector.EuropePMCSearchSource(
            source_operation=self.prep_operation
        )
        EuropePMCSearchSource.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )
        return record
