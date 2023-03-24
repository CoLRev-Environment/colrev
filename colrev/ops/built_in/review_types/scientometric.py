#! /usr/bin/env python
"""Scientometric study"""
from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


@zope.interface.implementer(
    colrev.env.package_manager.ReviewTypePackageEndpointInterface
)
@dataclass
class ScientometricReview(JsonSchemaMixin):
    """Scientometric study"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    def __init__(
        self, *, operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __str__(self) -> str:
        return "scientometric study"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a scientometric study"""

        settings.data.data_package_endpoints = [
            {
                "endpoint": "colrev.paper_md",
                "version": "1.0",
                "word_template": "APA-7.docx",
            }
        ]
        settings.pdf_get.pdf_required_for_screen_and_synthesis = False
        return settings


if __name__ == "__main__":
    pass
