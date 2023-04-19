#! /usr/bin/env python
"""Consolidation of metadata based on Europe PMC API as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.europe_pmc as europe_pmc_connector
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
class EuropePMCMetadataPrep(JsonSchemaMixin):
    """Prepares records based on Europe PCM metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "ask the publisher to correct the metadata"
    always_apply_changes = False

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
        """Prepare a record based on Europe PMC metadata"""

        # pylint: disable=invalid-name
        EuropePMCSearchSource = europe_pmc_connector.EuropePMCSearchSource(
            source_operation=prep_operation
        )
        EuropePMCSearchSource.get_masterdata(
            prep_operation=prep_operation, record=record
        )
        return record


if __name__ == "__main__":
    pass
