#! /usr/bin/env python
"""Consolidation of metadata based on GitHub REST API as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.packages.github.src.github_search_source as github_connector
import colrev.record.record
from colrev.constants import Fields


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.PrepInterface)
@dataclass
class GithubMetadataPrep(JsonSchemaMixin):
    """Prepares records based on GitHub metadata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "ask the publisher to correct the metadata"
    always_apply_changes = False
    docs_link = ()

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.prep_operation = prep_operation
        self.review_manager = prep_operation.review_manager

    def prepare(
            self, record: colrev.record.record_prep.PrepRecord
        ) -> colrev.record.record.Record:
        """Prepare a record based on GitHub metadata"""

        GitHubSearchSource = github_connector.GitHubSearchSource(
            source_operation=self.prep_operation
        )
        GitHubSearchSource.prep_link_md(
            prep_operation=self.prep_operation, record=record
        )
        return record

    