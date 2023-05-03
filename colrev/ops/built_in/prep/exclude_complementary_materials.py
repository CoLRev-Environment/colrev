#! /usr/bin/env python
"""Exclude complementary materials as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from alphabet_detector import AlphabetDetector
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

# pylint: disable=duplicate-code
if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class ExcludeComplementaryMaterialsPrep(JsonSchemaMixin):
    """Prepares records by excluding complementary materials
    (tables of contents, editorial boards, about our authors)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = True
    alphabet_detector = AlphabetDetector()

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.complementary_materials_keywords = (
            colrev.env.utils.load_complementary_material_keywords()
        )

        # for exact matches:
        self.complementary_materials_strings = (
            colrev.env.utils.load_complementary_material_strings()
        )

    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare the records by excluding complementary materials"""

        if any(
            complementary_materials_keyword in record.data.get("title", "").lower()
            for complementary_materials_keyword in self.complementary_materials_keywords
        ) or any(
            complementary_materials_string == record.data.get("title", "").lower()
            for complementary_materials_string in self.complementary_materials_strings
        ):
            record.prescreen_exclude(reason="complementary material")

        return record


if __name__ == "__main__":
    pass
