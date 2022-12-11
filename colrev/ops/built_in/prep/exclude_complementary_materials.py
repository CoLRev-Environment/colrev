#! /usr/bin/env python
"""Exclude complementary materials as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import timeout_decorator
import zope.interface
from alphabet_detector import AlphabetDetector
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class ExcludeComplementaryMaterialsPrep(JsonSchemaMixin):
    """Prepares records by excluding complementary materials
    (tables of contents, editorial boards, about our authors)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = True
    alphabet_detector = AlphabetDetector()

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare the records by excluding complementary materials"""

        # TODO : consolidate with scope.prescreen / title_complementary_materials_keywords

        complementary_materials_keywords = [
            "author index",
            "call for papers",
            "about authors",
            "about our authors",
            "subject index to volume",
            "information for authors",
            "instructions to authors",
            "authors index to volume",
            "acknowledgment of reviewers",
            "acknowledgment to reviewers",
        ]
        # for exact matches:
        complementary_materials_strings = [
            "editorial board",
            "calendar",
            "announcement",
            "announcements",
            "events",
            "international board of editors",
            "index",
            "subject index",
            "issue information",
            "keyword index",
            "about the authors",
            "thanks to reviewers",
        ]
        # TODO : allow users to override the default lists (based on settings)

        if any(
            complementary_materials_keyword in record.data.get("title", "").lower()
            for complementary_materials_keyword in complementary_materials_keywords
        ) or any(
            complementary_materials_string == record.data.get("title", "").lower()
            for complementary_materials_string in complementary_materials_strings
        ):
            record.prescreen_exclude(reason="complementary material")

        return record


if __name__ == "__main__":
    pass
