#! /usr/bin/env python
"""Methodological review"""
from pydantic import Field

import colrev.ops.search
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


class MethodologicalReview(base_classes.ReviewTypePackageBaseClass):
    """Methodological review"""

    ci_supported: bool = Field(default=True)
    settings_class: colrev.package_manager.package_settings.DefaultSettings

    def __init__(
        self, *, operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.settings = self.settings_class(**settings)

    def __str__(self) -> str:
        return "methodological review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a methodological review"""

        settings.data.data_package_endpoints = [
            {"endpoint": "colrev.prisma", "version": "1.0"},
            {
                "endpoint": "colrev.structured",
            },
            {
                "endpoint": "colrev.paper_md",
                "version": "1.0",
                "word_template": "APA-7.docx",
            },
        ]
        return settings
