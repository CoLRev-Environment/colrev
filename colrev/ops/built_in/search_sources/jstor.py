#! /usr/bin/env python
"""SearchSource: JSTOR"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.load_utils_ris
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class JSTORSearchSource(JsonSchemaMixin):
    """JSTOR"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.jstor"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "JSTOR"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/jstor.md"
    )
    db_url = "http://www.jstor.org"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for JSTOR"""

        result = {"confidence": 0.1}

        if "www.jstor.org:" in data:
            if data.count("www.jstor.org") > data.count("\n@"):
                result["confidence"] = 1.0
        if data.startswith("Provider: JSTOR http://www.jstor.org"):
            result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        return operation.add_db_source(
            search_source_cls=cls,
            params=params,
        )

    def run_search(self, rerun: bool) -> None:
        """Run a search of JSTOR"""

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            self.operation.run_db_search()  # type: ignore
            return

        raise NotImplementedError

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def __ris_fixes(self, *, entries: dict) -> None:
        for entry in entries:
            if "title" in entry and "primary_title" not in entry:
                entry["primary_title"] = entry.pop("title")

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".ris":
            ris_loader = colrev.ops.load_utils_ris.RISLoader(
                load_operation=load_operation,
                source=self.search_source,
                unique_id_field="jstor_id",
            )
            ris_entries = ris_loader.load_ris_entries()
            for ris_entry in ris_entries:
                ris_entry["jstor_id"] = ris_entry["url"].split("/")[-1]
            self.__ris_fixes(entries=ris_entries)
            records = ris_loader.convert_to_records(entries=ris_entries)
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for JSTOR"""

        return record
