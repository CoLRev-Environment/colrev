#! /usr/bin/env python
"""Consolidation of metadata based on Europe PMC API as a prep operation"""
from __future__ import annotations

import logging
import typing

from anyio import Path
from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.europe_pmc.src.europe_pmc as europe_pmc_connector
import colrev.record.record
import colrev.search_file
from colrev.constants import SearchType


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class EuropePMCMetadataPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on Europe PCM metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=True)

    source_correction_hint = "ask the publisher to correct the metadata"
    always_apply_changes = False
    _europe_pmc_md_filename = Path("data/search/md_europe_pmc.bib")

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

        europe_pmc_md_source_l = [
            s
            for s in prep_operation.review_manager.settings.sources
            if s.search_results_path == self._europe_pmc_md_filename
        ]
        if europe_pmc_md_source_l:
            search_file = europe_pmc_md_source_l[0]
        else:
            search_file = colrev.search_file.ExtendedSearchFile(
                platform="colrev.europe_pmc",
                search_results_path=self._europe_pmc_md_filename,
                search_type=SearchType.MD,
                search_string="",
                comment="",
                version="0.1.0",
            )

        self.epmc_source = europe_pmc_connector.EuropePMCSearchSource(
            search_file=search_file,
        )

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare a record based on Europe PMC metadata"""

        self.epmc_source.prep_link_md(prep_operation=self.prep_operation, record=record)
        return record
