#! /usr/bin/env python
"""Blank literature review"""
from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.ops.search
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.package_manager.interfaces.ReviewTypeInterface)
@dataclass
class BlankReview(JsonSchemaMixin):
    """Blank review"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = True

    def __init__(
        self, *, operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __str__(self) -> str:
        return "blank review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a blank review"""

        settings.data.data_package_endpoints = []
        settings.sources = []
        settings.prep.prep_rounds[0].prep_package_endpoints = []
        settings.prep.prep_man_package_endpoints = []
        settings.dedupe.dedupe_package_endpoints = []
        settings.prescreen.prescreen_package_endpoints = []
        settings.pdf_get.pdf_required_for_screen_and_synthesis = False
        settings.pdf_get.pdf_get_package_endpoints = []
        settings.pdf_get.pdf_get_man_package_endpoints = []
        settings.pdf_prep.pdf_prep_package_endpoints = []
        settings.pdf_prep.pdf_prep_man_package_endpoints = []
        settings.screen.screen_package_endpoints = []
        settings.data.data_package_endpoints = []

        return settings
