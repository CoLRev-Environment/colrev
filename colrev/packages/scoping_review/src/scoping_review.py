#! /usr/bin/env python
"""Scoping review"""
from pydantic import Field

import colrev.ops.search
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


class ScopingReview(base_classes.ReviewTypePackageBaseClass):
    """Scoping review"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = Field(default=True)

    def __init__(
        self, *, operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.settings = self.settings_class(**settings)

    def __str__(self) -> str:
        return "scoping review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a scoping review"""

        settings.data.data_package_endpoints = [
            {"endpoint": "colrev_prisma", "version": "1.0"},
            {
                "endpoint": "colrev_structured",
            },
            {
                "endpoint": "colrev_paper_md",
                "version": "1.0",
                "word_template": "APA-7.docx",
            },
        ]
        return settings
