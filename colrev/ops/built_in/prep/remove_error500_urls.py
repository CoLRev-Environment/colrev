#! /usr/bin/env python
"""Removal of broken URLs (error 500) a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class RemoveError500URLsPrep(JsonSchemaMixin):
    """Prepares records by removing urls that are not available"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record by removing URLs with 500 errors"""

        session = prep_operation.review_manager.get_cached_session()

        try:
            if Fields.URL in record.data:
                ret = session.request(
                    "GET",
                    record.data[Fields.URL],
                    headers=prep_operation.requests_headers,
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
                    headers=prep_operation.requests_headers,
                    timeout=prep_operation.timeout,
                )
                if ret.status_code >= 500:
                    record.remove_field(key=Fields.FULLTEXT)
        except requests.exceptions.RequestException:
            pass

        return record
