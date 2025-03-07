#! /usr/bin/env python
"""Theoretical review"""
from pydantic import Field

import colrev.ops.search
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


# @zope.interface.implementer(base_classes.ReviewTypePackageBaseClass)
class TheoreticalReview(base_classes.ReviewTypePackageBaseClass):
    """Theoretical review"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=True)

    def __init__(
        self, *, operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.settings = self.settings_class(**settings)

    def __str__(self) -> str:
        return "theoretical review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a theoretical review"""

        settings.data.data_package_endpoints = [
            {
                "endpoint": "colrev.obsidian",
                "version": "0.1",
                "config": {},
            },
            {
                "endpoint": "colrev.paper_md",
                "version": "1.0",
                "word_template": "APA-7.docx",
            },
        ]
        return settings
