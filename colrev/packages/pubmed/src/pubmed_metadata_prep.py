#! /usr/bin/env python
"""Consolidation of metadata based on the Pubmed API as a prep operation"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.pubmed.src.pubmed as pubmed_connector
import colrev.record.record
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import SearchType

# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class PubmedMetadataPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on Pubmed metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=True)

    source_correction_hint = "ask the publisher to correct the metadata"
    always_apply_changes = False
    _pubmed_md_filename = Path("data/search/md_pubmed.bib")

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

        pubmed_md_source_l = [
            s
            for s in self.prep_operation.review_manager.settings.sources
            if s.search_results_path == self._pubmed_md_filename
        ]
        if pubmed_md_source_l:
            search_file = pubmed_md_source_l[0]
        else:
            search_file = colrev.search_file.ExtendedSearchFile(
                platform="colrev.pubmed",
                search_results_path=self._pubmed_md_filename,
                search_type=SearchType.MD,
                search_string="",
                comment="",
                version="0.1.0",
            )

        self.pubmed_source = pubmed_connector.PubMedSearchSource(
            search_file=search_file
        )

        self.pubmed_prefixes = [
            s.get_origin_prefix()
            for s in prep_operation.review_manager.settings.sources
            if s.platform == "colrev.pubmed"
        ]

    def check_availability(self) -> None:
        """Check status (availability) of the Pubmed API"""
        self.pubmed_source.check_availability()

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare a record based on Pubmed metadata"""

        if any(
            pubmed_prefix in o
            for pubmed_prefix in self.pubmed_prefixes
            for o in record.data[Fields.ORIGIN]
        ):
            # Already linked to a pubmed record
            return record

        self.pubmed_source.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )
        return record
