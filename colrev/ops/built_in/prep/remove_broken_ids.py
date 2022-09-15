#! /usr/bin/env python
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageInterface)
class RemoveBrokenIDPrep:
    """Prepares records by removing invalid IDs DOIs/ISBNs"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    # check_status: relies on crossref / openlibrary connectors!
    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:

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
