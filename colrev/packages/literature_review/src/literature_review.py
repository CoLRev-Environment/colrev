#! /usr/bin/env python
"""Simple literature review"""
import logging
import typing

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


#
class LiteratureReview(base_classes.ReviewTypePackageBaseClass):
    """Literature review (simple)"""

    ci_supported: bool = Field(default=True)
    settings: colrev.package_manager.package_settings.DefaultSettings
    settings_class = colrev.package_manager.package_settings.DefaultSettings

    def __init__(
        self,
        *,
        operation: colrev.process.operation.Operation,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)

    def __str__(self) -> str:
        return "literature review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a literature review"""

        settings.data.data_package_endpoints = [
            {
                "endpoint": "colrev.paper_md",
                "version": "1.0",
                "word_template": "APA-7.docx",
            }
        ]
        return settings
