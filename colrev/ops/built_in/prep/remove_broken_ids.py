#! /usr/bin/env python
"""Removal of broken IDs as a prep operation"""
from __future__ import annotations

import re
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
class RemoveBrokenIDPrep(JsonSchemaMixin):
    """Prepares records by removing invalid IDs DOIs/ISBNs"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    # check_status: relies on crossref / openlibrary connectors!
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
        """Prepare the record by removing broken IDs (invalid DOIs/ISBNs)"""

        if prep_operation.polish and not prep_operation.force_mode:
            return record

        if "doi" in record.data:
            # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
            doi_match = re.match(r"^10.\d{4,9}\/", record.data["doi"])
            if not doi_match:
                record.remove_field(key="doi")
        if "isbn" in record.data:
            try:
                session = prep_operation.review_manager.get_cached_session()

                isbn = record.data["isbn"].replace("-", "").replace(" ", "")
                url = f"https://openlibrary.org/isbn/{isbn}.json"
                ret = session.request(
                    "GET",
                    url,
                    headers=prep_operation.requests_headers,
                    timeout=prep_operation.timeout,
                )
                ret.raise_for_status()
            except requests.exceptions.RequestException:
                record.remove_field(key="isbn")
        return record


if __name__ == "__main__":
    pass
