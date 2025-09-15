#! /usr/bin/env python
"""Removal of broken URLs (error 500) a prep operation"""
from __future__ import annotations

import logging
import typing

import requests
from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.utils
from colrev.constants import Fields


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class RemoveError500URLsPrep(base_classes.PrepPackageBaseClass):
    """Prepares records by removing urls that are not available"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=True)

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    requests_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
    }

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)
        self.prep_operation = prep_operation
        self.review_manager = prep_operation.review_manager

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Prepare the record by removing URLs with 500 errors"""

        session = colrev.utils.get_cached_session()

        try:
            if Fields.URL in record.data:
                ret = session.request(
                    "GET",
                    record.data[Fields.URL],
                    headers=self.requests_headers,
                    timeout=60,
                )
                if ret.status_code >= 500:
                    record.remove_field(key=Fields.URL)
        except requests.exceptions.RequestException:
            pass
        try:
            if Fields.FULLTEXT in record.data:
                ret = session.request(
                    "GET",
                    record.data[Fields.FULLTEXT],
                    headers=self.requests_headers,
                    timeout=self.prep_operation.timeout,
                )
                if ret.status_code >= 500:
                    record.remove_field(key=Fields.FULLTEXT)
        except requests.exceptions.RequestException:
            pass

        return record
