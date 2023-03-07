#! /usr/bin/env python
"""Template for a custom SearchSource PackageEndpoint"""
from __future__ import annotations

from pathlib import Path

import zope.interface
from dacite import from_dict

import colrev.exceptions as colrev_exceptions
import colrev.operation

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.search.Search


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
class CustomSearch:
    """Class for custom search scripts"""

    settings_class = colrev.env.package_manager.DefaultSettings
    source_identifier = "custom"

    def __init__(
        self,
        *,
        source_operation: colrev.ops.search.Search,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(
        self,
        search_operation: colrev.ops.search.Search,
        params: dict,  # pylint: disable=unused-argument
        feed_file: Path,
    ) -> None:
        """Run the search"""

        max_id = 1
        if not feed_file.is_file():
            records = {}
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                records = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            max_id = (
                max([int(x["ID"]) for x in records.values() if x["ID"].isdigit()] + [1])
                + 1
            )

        # Add new records to the dictionary:
        records[max_id] = {
            "ID": max_id,
            "ENTRYTYPE": "article",
            "author": "Smith, M.",
            "title": "Editorial",
            "journal": "nature",
            "year": "2020",
        }

        feed_file.parents[0].mkdir(parents=True, exist_ok=True)
        search_operation.review_manager.dataset.save_records_dict_to_file(
            records=records, save_path=feed_file
        )

    @classmethod
    def validate_search_params(cls, query: str) -> None:
        """Validate the search parameters"""

        if " SCOPE " not in query:
            raise colrev_exceptions.InvalidQueryException(
                "CROSSREF queries require a SCOPE section"
            )

        scope = query[query.find(" SCOPE ") :]
        if "journal_issn" not in scope:
            raise colrev_exceptions.InvalidQueryException(
                "CROSSREF queries require a journal_issn field in the SCOPE section"
            )

    def heuristic(
        self, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        """Heuristic to identify the custom source"""

        result = {"confidence": 0}

        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,  # pylint: disable=unused-argument
        source: colrev.settings.SearchSource,  # pylint: disable=unused-argument
        records: dict,
    ) -> dict:
        """Load fixes for the custom source"""

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        """Source-specific preparation for the custom source"""

        return record
