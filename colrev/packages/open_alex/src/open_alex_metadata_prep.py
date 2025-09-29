#! /usr/bin/env python
"""Consolidation of metadata based on OpenAlex API as a prep operation"""
from __future__ import annotations

import logging
import typing

from anyio import Path
from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.open_alex.src.open_alex as open_alex_connector
import colrev.record.record
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import SearchType


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class OpenAlexMetadataPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on OpenAlex metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = Field(default=True)

    source_correction_hint = "TBD"
    always_apply_changes = False
    _open_alex_md_filename = Path("data/search/md_open_alex.bib")

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

        open_alex_md_source_l = [
            s
            for s in self.prep_operation.review_manager.settings.sources
            if s.filename == self._open_alex_md_filename
        ]
        if open_alex_md_source_l:
            search_file = open_alex_md_source_l[0]
        else:
            search_file = colrev.search_file.ExtendedSearchFile(
                platform="colrev.open_alex",
                search_results_path=self._open_alex_md_filename,
                search_type=SearchType.MD,
                search_string="",
                comment="",
                version="0.1.0",
            )

        self.open_alex_source = open_alex_connector.OpenAlexSearchSource(
            search_file=search_file
        )

        self.open_alex_prefixes = [
            s.get_origin_prefix()
            for s in prep_operation.review_manager.settings.sources
            if s.endpoint == "colrev.open_alex"
        ]

    def check_availability(self) -> None:
        """Check status (availability) of the OpenAlex API"""
        self.open_alex_source.check_availability()

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare a record based on OpenAlex metadata"""

        if any(
            crossref_prefix in o
            for crossref_prefix in self.open_alex_prefixes
            for o in record.data[Fields.ORIGIN]
        ):
            # Already linked to an OpenAlex record
            return record

        self.open_alex_source.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )
        return record
