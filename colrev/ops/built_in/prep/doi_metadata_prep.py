#! /usr/bin/env python
"""Consolidation of metadata based on DOI metadata as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.doi_org as doi_connector
import colrev.ops.search_sources
import colrev.record
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class DOIMetadataPrep(JsonSchemaMixin):
    """Prepares records based on doi.org metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.prep_operation = prep_operation
        self.review_manager = prep_operation.review_manager

    def prepare(self, record: colrev.record.PrepRecord) -> colrev.record.Record:
        """Prepare the record by retrieving its metadata from doi.org"""

        if Fields.DOI not in record.data:
            return record
        doi_connector.DOIConnector.retrieve_doi_metadata(
            review_manager=self.review_manager,
            record=record,
            timeout=self.prep_operation.timeout,
        )
        doi_connector.DOIConnector.get_link_from_doi(
            record=record,
            review_manager=self.review_manager,
        )
        return record
