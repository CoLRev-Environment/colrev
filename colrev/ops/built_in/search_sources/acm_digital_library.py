#! /usr/bin/env python
"""SearchSource: ACM Digital Library"""
from __future__ import annotations

import typing
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
class ACMDigitalLibrarySearchSource(JsonSchemaMixin):
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    # Note : the ID contains the doi
    source_identifier = "https://dl.acm.org/doi/{{ID}}"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0.0}

        # Simple heuristic:
        if "publisher = {Association for Computing Machinery}," in data:
            result["confidence"] = 0.7
            return result
        # We may also check whether the ID=doi=url
        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


if __name__ == "__main__":
    pass
