#! /usr/bin/env python
"""Consolidation of metadata based on Crossref API as a prep operation"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.crossref.src.crossref_search_source as crossref_connector
import colrev.record.record
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import SearchType

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class CrossrefMetadataPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on crossref.org metadata"""

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

        # Crossref as an md-prep source
        crossref_md_filename = Path("data/search/md_crossref.bib")
        crossref_md_source_l = [
            s
            for s in self.prep_operation.review_manager.settings.sources
            if s.search_results_path == crossref_md_filename
        ]
        if crossref_md_source_l:
            search_file = crossref_md_source_l[0]
        else:
            search_file = colrev.search_file.ExtendedSearchFile(
                platform="colrev.crossref",
                search_results_path=crossref_md_filename,
                search_type=SearchType.MD,
                search_string="https://api.crossref.org/",  # dummy
                comment="",
                version=(
                    crossref_connector.CrossrefSearchSource.CURRENT_SYNTAX_VERSION
                ),
            )

        self.crossref_source = crossref_connector.CrossrefSearchSource(
            search_file=search_file,
        )

        self.crossref_prefixes = [
            s.get_origin_prefix()
            for s in prep_operation.review_manager.settings.sources
            if s.platform == "colrev.crossref"
        ]

    def check_availability(self) -> None:
        """Check status (availability) of the Crossref API"""
        self.crossref_source.check_availability()

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare a record based on Crossref metadata"""

        if any(
            crossref_prefix in o
            for crossref_prefix in self.crossref_prefixes
            for o in record.data[Fields.ORIGIN]
        ):
            # Already linked to a crossref record
            return record

        self.crossref_source.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )
        return record
