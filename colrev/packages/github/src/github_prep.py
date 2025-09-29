#! /usr/bin/env python
"""Consolidation of metadata based on GitHub REST API as a prep operation"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.packages.github.src.github_search_source as github_connector
import colrev.record.record
import colrev.search_file
from colrev.constants import SearchType


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class GithubMetadataPrep(base_classes.PrepPackageBaseClass):
    """Prepares records based on GitHub metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=True)

    source_correction_hint = "ask the publisher to correct the metadata"
    always_apply_changes = False
    docs_link = ()
    _github_md_filename = Path("data/search/md_github.bib")

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

        # GitHub as a md-prep source
        github_md_source_l = [
            s
            for s in prep_operation.review_manager.settings.sources
            if s.filename == self._github_md_filename
        ]
        if github_md_source_l:
            search_file = github_md_source_l[0]
        else:
            search_file = colrev.search_file.ExtendedSearchFile(
                platform="colrev.github",
                search_results_path=self._github_md_filename,
                search_type=SearchType.MD,
                search_string="",
                comment="",
                version="0.1.0",
            )

        self.github_search_source = github_connector.GitHubSearchSource(
            search_file=search_file
        )

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare a record based on GitHub metadata"""

        self.github_search_source.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )
        return record
