#! /usr/bin/env python
"""SearchSource: Unknown source (default for all other sources)"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import dacite
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class UnknownSearchSource(JsonSchemaMixin):

    settings_class = colrev.env.package_manager.DefaultSourceSettings

    source_identifier = "colrev_built_in.unknown_source"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:

        converters = {Path: Path, Enum: Enum}
        self.settings = from_dict(
            data_class=self.settings_class,
            data=settings,
            config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for unknown sources"""

        # TODO
        result = {"confidence": 0.0}

        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of an unknown source"""

        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for unknown sources"""

        return records

    def prepare(self, record: colrev.record.PrepRecord) -> colrev.record.Record:
        """Source-specific preparation for unknown sources"""

        return record


if __name__ == "__main__":
    pass
