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
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class UnknownSearchSource(JsonSchemaMixin):
    """SearchSource for unknown search results"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings

    source_identifier = "colrev_built_in.unknown_source"
    search_type = colrev.settings.SearchType.DB
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.na
    short_name = "Unknown Source"
    link = (
        "https://github.com/geritwagner/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/unknown_source.py"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:

        converters = {Path: Path, Enum: Enum}
        self.search_source = from_dict(
            data_class=self.settings_class,
            data=settings,
            config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for unknown sources"""

        result = {"confidence": 0.0}

        return result

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        # Note : source_identifier is not restricted

        if "query_file" in source.search_parameters:
            if not Path(source.search_parameters["query_file"]).is_file():
                raise colrev_exceptions.InvalidQueryException(
                    f"File does not exist: query_file {source.search_parameters['query_file']} "
                    f"for ({source.filename})"
                )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for unknown sources"""

        return records

    def prepare(
        self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for unknown sources"""

        if (
            "colrev_built_in.md_to_bib"
            == source.load_conversion_package_endpoint["endpoint"]
        ):
            if "misc" == record.data["ENTRYTYPE"] and "publisher" in record.data:
                record.data["ENTRYTYPE"] = "book"
            if record.data.get("year", "year") == record.data.get("date", "date"):
                record.remove_field(key="date")
            if (
                "inbook" == record.data["ENTRYTYPE"]
                and "chapter" not in record.data
                and "title" in record.data
            ):
                record.rename_field(key="title", new_key="chapter")

        return record


if __name__ == "__main__":
    pass
