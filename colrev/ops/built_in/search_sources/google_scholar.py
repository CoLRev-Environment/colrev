#! /usr/bin/env python
"""SearchSource: GoogleScholar"""
from pathlib import Path

import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.SearchSourcePackageInterface)
class GoogleScholarSearchSource:
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "https://scholar.google.com/"

    source_identifier_search = "https://scholar.google.com/"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        if "related = {https://scholar.google.com/scholar?q=relat" in data:
            result["confidence"] = 0.7
            return result
        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


if __name__ == "__main__":
    pass
