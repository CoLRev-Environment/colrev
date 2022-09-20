#! /usr/bin/env python
"""SearchSource: Wiley"""
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.SearchSourcePackageInterface)
@dataclass
class WileyOnlineLibrarySearchSource(JsonSchemaMixin):
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{url}}"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0.0}

        # Simple heuristic:
        if "eprint = {https://onlinelibrary.wiley.com/doi/pdf/" in data:
            result["confidence"] = 0.7
            return result

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


if __name__ == "__main__":
    pass
