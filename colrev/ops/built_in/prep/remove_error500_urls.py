#! /usr/bin/env python
"""Removal of broken URLs (error 500) a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

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
            if "url" in record.data:
                ret = session.request(
                    "GET",
                    record.data["url"],
                    headers=prep_operation.requests_headers,
                    timeout=60,
                )
                if ret.status_code >= 500:
                    record.remove_field(key="url")
        except requests.exceptions.RequestException:
            pass
        try:
            if "fulltext" in record.data:
                ret = session.request(
                    "GET",
                    record.data["fulltext"],
                    headers=prep_operation.requests_headers,
                    timeout=prep_operation.timeout,
                )
                if ret.status_code >= 500:
                    record.remove_field(key="fulltext")
        except requests.exceptions.RequestException:
            pass

        return record


if __name__ == "__main__":
    pass
