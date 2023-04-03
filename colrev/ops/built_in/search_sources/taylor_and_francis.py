#! /usr/bin/env python
"""SearchSource: Taylor and Francis"""
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
class TaylorAndFrancisSearchSource(JsonSchemaMixin):
    """SearchSource for Taylor and Francis"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{doi}}"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = False
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "Taylor and Francis"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/taylor_and_francis.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Taylor and Francis"""

        result = {"confidence": 0.0}

        if data.count("\n@") > 1:
            if data.count("eprint = { \n    \n    ") >= data.count("\n@"):
                result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        return None

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of TaylorAndFrancis"""

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for Taylor and Francis"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Taylor and Francis"""

        # remove eprint and URL fields (they only have dois...)
        record.remove_field(key="url")
        record.remove_field(key="eprint")

        return record


if __name__ == "__main__":
    pass
