#! /usr/bin/env python
"""SearchSource: PsycINFO"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from rispy import BaseParser
from rispy.config import LIST_TYPE_TAGS
from rispy.config import TAG_KEY_MAPPING

import colrev.env.package_manager
import colrev.ops.load_utils_ris
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class PsycInfoRISParser(BaseParser):
    """Parser for Psycinfo RIS files."""

    START_TAG = "TY"
    IGNORE = ["FN", "VR", "EF"]
    PATTERN = r"^[A-Z][A-Z0-9]+ |^ER\s?|^EF\s?"
    mapping = deepcopy(TAG_KEY_MAPPING)
    # mapping["A1"] = "authors"
    mapping["PM"] = "pubmedid"
    # mapping["T1"] = "primary_title"
    # mapping["JF"] = "secondary_title"
    DEFAULT_MAPPING = mapping
    DEFAULT_LIST_TAGS = LIST_TYPE_TAGS

    def get_content(self, line: str) -> str:
        "Get the content from a line."
        return line[line.find(" - ") + 2 :].strip()

    def is_header(self, line: str) -> bool:
        "Check whether the line is a header element"
        return not re.match("[A-Z0-9]+  - ", line)


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class PsycINFOSearchSource(JsonSchemaMixin):
    """PsycINFO"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.psycinfo"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    short_name = "PsycInfo (APA)"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/psycinfo.md"
    )
    db_url = "https://www.apa.org/search"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for PsycINFO"""

        result = {"confidence": 0.1}

        # Note : no features in bib file for identification

        if data.startswith(
            "Provider: American Psychological Association\nDatabase: PsycINFO"
        ):
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
        """Run a search of Psycinfo"""

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

    def __ris_fixes(self, *, entries: dict) -> None:
        for entry in entries:
            if "alternate_title3" in entry and entry["type_of_reference"] in ["JOUR"]:
                entry["secondary_title"] = entry.pop("alternate_title3")
            if "publication_year" in entry:
                entry["year"] = entry.pop("publication_year")
            if "first_authors" in entry and "authors" not in entry:
                entry["authors"] = entry.pop("first_authors")

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".ris":
            ris_loader = colrev.ops.load_utils_ris.RISLoader(
                load_operation=load_operation,
                source=self.search_source,
                ris_parser=PsycInfoRISParser,
            )
            ris_entries = ris_loader.load_ris_entries()
            self.__ris_fixes(entries=ris_entries)
            records = ris_loader.convert_to_records(entries=ris_entries)
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for PsycINFO"""

        return record
