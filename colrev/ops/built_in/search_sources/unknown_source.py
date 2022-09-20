#! /usr/bin/env python
"""SearchSource: Unknown source (default for all other sources)"""
from enum import Enum
from pathlib import Path

import dacite
import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.SearchSourcePackageInterface)
class UnknownSearchSource:

    settings_class = colrev.env.package_manager.DefaultSourceSettings

    source_identifier = "unknown_source"
    source_identifier_search = "unknown_source"
    search_mode = "individual"

    def __init__(self, *, source_operation, settings: dict) -> None:
        converters = {Path: Path, Enum: Enum}
        self.settings = from_dict(
            data_class=self.settings_class,
            data=settings,
            config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
        )
        converters = {Path: Path, Enum: Enum}
        self.settings = from_dict(
            data_class=self.settings_class,
            data=settings,
            config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        # TODO
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.PrepRecord) -> colrev.record.Record:

        return record


if __name__ == "__main__":
    pass
