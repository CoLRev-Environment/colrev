#! /usr/bin/env python
"""Consolidation of metadata based on Plos API as a prep operation"""
from __future__ import annotations

import zope.interface
from pydantic import Field

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.packages.plos.src.plos_search_source as plos_connector
import colrev.process
import colrev.process.operation
import colrev.record.record
from colrev.constants import Fields
import colrev.record.record_prep


@zope.interface.implementer(colrev.package_manager.interfaces.PrepInterface)
class PlosMetadataPrep:
    """Prepares records based on plos.org metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=True)

    #source_correction_hint = (
#
    #)

    always_apply_changes = False

    def __init__(
            self, 
            *, 
            prep_operation: colrev.ops.prep.Prep, 
            settings: dict
    ) -> None:
        print("Initializing PlosMetadataPrep...")

        self.settings = self.settings_class(**settings)
        self.prep_operation = prep_operation
        self.plos_source = plos_connector.PlosSearchSource(
            source_operation=prep_operation
        )

        self.plos_prefixes = [
            s.get_origin_prefix()
            for s in prep_operation.review_manager.settings.sources
            if s.endpoint == "colrev.plos"
        ]

    def check_availability(
            self, *, source_operation: colrev.process.operation.Operation
    ) -> None:
        """Check status (availability) of the Plos API"""

        self.plos_source.check_availability(source_operation=source_operation)

    
    def prepare(
            self, record: colrev.record.record_prep.PrepRecord
    ) -> colrev.record.record.Record:
        "Prepare a record based on PLOS metadata"
        
        if any(
            plos_prefix in o 
            for plos_prefix in self.plos_prefixes
            for o in record.data[Fields.ORIGIN]
        ):
            return record
        
        self.plos_source.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )

        return record
