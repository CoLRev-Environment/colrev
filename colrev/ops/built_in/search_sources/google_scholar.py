#! /usr/bin/env python
"""SearchSource: GoogleScholar"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search
import colrev.record


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class GoogleScholarSearchSource(JsonSchemaMixin):
    """SearchSource for GoogleScholar"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "https://scholar.google.com/"
    search_type = colrev.settings.SearchType.DB

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for GoogleScholar"""

        result = {"confidence": 0.0}
        if "related = {https://scholar.google.com/scholar?q=relat" in data:
            result["confidence"] = 0.7
            return result
        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of GoogleScholar"""

        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for GoogleScholar"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for GoogleScholar"""

        return record


if __name__ == "__main__":
    pass
