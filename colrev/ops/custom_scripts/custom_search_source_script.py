#! /usr/bin/env python
"""Template for a custom SearchSource PackageEndpoint"""
from __future__ import annotations

import logging
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
from colrev.constants import Fields


class CustomSearch(base_classes.SearchSourcePackageBaseClass):
    """Class for custom search scripts"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    source_identifier = "custom"

    def __init__(
        self,
        *,
        settings: colrev.search_file.ExtendedSearchFile,
    ) -> None:
        self.search_source: colrev.search_file.ExtendedSearchFile = settings

    def search(self, rerun: bool) -> None:
        """Run the search"""

        feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=logging.getLogger(__name__),
            verbose_mode=False,
        )
        retrieved_record = {
            Fields.ID: "ID00001",
            Fields.ENTRYTYPE: "article",
            Fields.AUTHOR: "Smith, M.",
            Fields.TITLE: "Editorial",
            Fields.JOURNAL: "nature",
            Fields.YEAR: "2020",
        }

        feed.add_update_record(colrev.record.record.Record(retrieved_record))
        feed.save()

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

    @classmethod
    def heuristic(
        cls, filename: Path, data: str  # pylint: disable=unused-argument
    ) -> dict:
        """Heuristic to identify the custom source"""

        result = {"confidence": 0}

        return result

    def load(self) -> dict:
        """Load fixes for the custom source"""
        records = {"ID1": {"ID": "ID1", "title": "..."}}

        return records

    def prepare(
        self,
        record: colrev.record.record.Record,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for the custom source"""

        return record
