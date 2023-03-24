#! /usr/bin/env python
"""Critical review"""
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
class CriticalReview(JsonSchemaMixin):
    """Critical review"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    def __init__(
        self, *, operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __str__(self) -> str:
        return "critical review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a critical review"""

        settings.data.data_package_endpoints = [
            {"endpoint": "colrev.prisma", "version": "1.0"},
            {
                "endpoint": "colrev.paper_md",
                "version": "1.0",
                "word_template": "APA-7.docx",
            },
        ]

        return settings


if __name__ == "__main__":
    pass
