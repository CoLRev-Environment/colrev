#! /usr/bin/env python
"""SearchSource: Taylor and Francis"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.load_utils_bib
import colrev.ops.search
import colrev.record
from colrev.constants import Fields

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class TaylorAndFrancisSearchSource(JsonSchemaMixin):
    """Taylor and Francis"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.taylor_and_francis"
    source_identifier = "{{doi}}"
    search_types = [colrev.settings.SearchType.DB]
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "Taylor and Francis"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/taylor_and_francis.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager
        self.operation = source_operation

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
        """Run a search of TaylorAndFrancis"""

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            self.operation.run_db_search()  # type: ignore

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Taylor and Francis"""

        # remove eprint and URL fields (they only have dois...)
        record.remove_field(key="colrev.taylor_and_francis.eprint")
        if "colrev.taylor_and_francis.note" in record.data and re.match(
            r"PMID: \d*", record.data["colrev.taylor_and_francis.note"]
        ):
            record.rename_field(
                key="colrev.taylor_and_francis.note", new_key=Fields.PUBMED_ID
            )
            record.data[Fields.PUBMED_ID] = record.data[Fields.PUBMED_ID][6:]

        return record
