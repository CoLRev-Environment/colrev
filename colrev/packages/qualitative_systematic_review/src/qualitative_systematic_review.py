#! /usr/bin/env python
"""Qualitative systematic review"""
import logging
import typing

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
from colrev.packages.open_citations_forward_search.src.open_citations_forward_search import (
    OpenCitationsSearchSource,
)
from colrev.packages.pdf_backward_search.src.pdf_backward_search import (
    BackwardSearchSource,
)

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


class QualitativeSystematicReview(base_classes.ReviewTypePackageBaseClass):
    """Qualitative systematic review"""

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
        return "qualitative systematic review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a qualitative systematic review"""

        settings.sources.append(OpenCitationsSearchSource.get_default_source())
        settings.sources.append(BackwardSearchSource.get_default_source())

        settings.data.data_package_endpoints = [
            {"endpoint": "colrev.prisma", "version": "1.0"},
            {
                "endpoint": "colrev.structured",
                "version": "1.0",
                "fields": [],
            },
            {
                "endpoint": "colrev.paper_md",
                "version": "1.0",
                "word_template": "APA-7.docx",
            },
        ]
        return settings
