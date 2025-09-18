#! /usr/bin/env python
"""Consolidation of metadata based on DOI metadata as a prep operation"""
from __future__ import annotations

import logging
import typing

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.doi_org.src.doi_org as doi_connector
import colrev.record.record
from colrev.constants import Fields


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class DOIMetadataPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on doi.org metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = Field(default=True)

    source_correction_hint = (
        "ask the publisher to correct the metadata"
        + " (see https://www.crossref.org/blog/"
        + "metadata-corrections-updates-and-additions-in-metadata-manager/"
    )
    always_apply_changes = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)
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
        """Prepare the record by retrieving its metadata from doi.org"""

        if Fields.DOI not in record.data:
            return record
        doi_connector.DOIConnector.retrieve_doi_metadata(
            record=record,
            logger=self.logger,
            timeout=self.prep_operation.timeout,
        )
        doi_connector.DOIConnector.get_link_from_doi(
            record=record,
        )
        return record
