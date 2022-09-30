#! /usr/bin/env python
"""SearchSource: Web of Science"""
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
class WebOfScienceSearchSource(JsonSchemaMixin):
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = (
        "https://www.webofscience.com/wos/woscc/full-record/" + "{{unique-id}}"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:

        result = {"confidence": 0.0}

        if "Unique-ID = {WOS:" in data:
            result["confidence"] = 0.7
            return result
        if "UT_(Unique_WOS_ID) = {WOS:" in data:
            result["confidence"] = 0.7
            return result
        if "@article{ WOS:" in data:
            result["confidence"] = 1.0
            return result

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

        return record


if __name__ == "__main__":
    pass
