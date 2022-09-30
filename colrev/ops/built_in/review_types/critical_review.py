#! /usr/bin/env python
"""Critical review"""
from dataclasses import dataclass

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.ReviewTypePackageInterface)
@dataclass
class CriticalReview(JsonSchemaMixin):

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self, *, operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def __str__(self) -> str:
        return "critical review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:

        settings.data.data_package_endpoints = [
            {
                "endpoint": "colrev_built_in.manuscript",
                "version": "1.0",
                "word_template": "APA-7.docx",
                "csl_style": "apa.csl",
            },
            {"endpoint": "colrev_built_in.prisma", "version": "1.0"},
        ]

        return settings


if __name__ == "__main__":
    pass
