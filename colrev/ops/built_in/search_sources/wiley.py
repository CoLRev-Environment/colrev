#! /usr/bin/env python
"""SearchSource: Wiley"""
from __future__ import annotations

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
class WileyOnlineLibrarySearchSource(JsonSchemaMixin):
    """Wiley"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.wiley"
    source_identifier = "url"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "Wiley"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/wiley.md"
    )
    db_url = "https://onlinelibrary.wiley.com/"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Wiley"""

        result = {"confidence": 0.0}

        # Simple heuristic:
        if "eprint = {https://onlinelibrary.wiley.com/doi/pdf/" in data:
            result["confidence"] = 0.7
            return result

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
        """Run a search of Wiley"""

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
            for record_dict in records.values():
                if "eprint" not in record_dict:
                    continue
                record_dict[Fields.FULLTEXT] = record_dict.pop("eprint")
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Wiley"""

        if record.data.get(Fields.ENTRYTYPE, "") == "inbook":
            record.rename_field(key=Fields.TITLE, new_key=Fields.CHAPTER)
            record.rename_field(key=Fields.BOOKTITLE, new_key=Fields.TITLE)

        return record
