#! /usr/bin/env python
"""Blank literature review"""
import logging
import typing

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


class BlankReview(base_classes.ReviewTypePackageBaseClass):
    """Blank review"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = Field(default=True)

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
