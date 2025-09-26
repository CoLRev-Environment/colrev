#! /usr/bin/env python
"""Consolidation of metadata based on OpenLibrary API as a prep operation"""
from __future__ import annotations

import logging
import typing

from anyio import Path
from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.open_library.src.open_library as open_library_connector
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import SearchType

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class OpenLibraryMetadataPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on openlibrary.org metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = Field(default=True)

    source_correction_hint = "ask the publisher to correct the metadata"
    always_apply_changes = False
    _open_library_md_filename = Path("data/search/md_open_library.bib")

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

        # OpenLibrary as an md-prep source
        open_library_md_source_l = [
            s
            for s in self.prep_operation.review_manager.settings.sources
            if s.search_results_path == self._open_library_md_filename
        ]
        if open_library_md_source_l:
            search_file = open_library_md_source_l[0]
        else:
            search_file = colrev.search_file.ExtendedSearchFile(
                platform="colrev.open_library",
                search_results_path=self._open_library_md_filename,
                search_type=SearchType.MD,
                search_string="",
                comment="",
                version="0.1.0",
            )

        self.open_library_connector = open_library_connector.OpenLibrarySearchSource(
            search_file=search_file
        )

    def check_availability(self) -> None:
        """Check status (availability) of the OpenLibrary API"""
        self.open_library_connector.check_availability()

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare the record metadata based on OpenLibrary"""

        if record.data.get(Fields.ENTRYTYPE, "NA") != "book":
            return record

        self.open_library_connector.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )

        return record
