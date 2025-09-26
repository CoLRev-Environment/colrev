#! /usr/bin/env python
"""Consolidation of metadata based on DBLP API as a prep operation"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.dblp.src.dblp as dblp_connector
import colrev.record.record
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import SearchType


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class DBLPMetadataPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on dblp.org metadata"""

    ci_supported: bool = Field(default=True)
    settings_class = colrev.package_manager.package_settings.DefaultSettings

    source_correction_hint = (
        "send and email to dblp@dagstuhl.de"
        + " (see https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html)"
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

        # DBLP as an md-prep source
        dblp_md_filename = Path("data/search/md_dblp.bib")
        dblp_md_source_l = [
            s
            for s in self.prep_operation.review_manager.settings.sources
            if s.search_results_path == dblp_md_filename
        ]
        if dblp_md_source_l:
            search_file = dblp_md_source_l[0]
        else:
            search_file = colrev.search_file.ExtendedSearchFile(
                platform="colrev.dblp",
                search_results_path=dblp_md_filename,
                search_type=SearchType.MD,
                search_string="",
                comment="",
                version="0.1.0",
            )

        self.dblp_source = dblp_connector.DBLPSearchSource(search_file=search_file)

        self.dblp_prefixes = [
            s.get_origin_prefix()
            for s in prep_operation.review_manager.settings.sources
            if s.search_results_path == "colrev.dblp"
        ]

    def check_availability(self) -> None:
        """Check status (availability) of the DBLP API"""
        self.dblp_source.check_availability()

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare a record by retrieving its metadata from DBLP"""

        if any(
            dblp_prefix in o
            for dblp_prefix in self.dblp_prefixes
            for o in record.data[Fields.ORIGIN]
        ):
            # Already linked to a dblp record
            return record

        self.dblp_source.prep_link_md(prep_operation=self.prep_operation, record=record)

        return record
