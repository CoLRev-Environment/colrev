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
import colrev.exceptions as colrev_exceptions
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
    """SearchSource for PsycINFO"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "url"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = False
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    short_name = "PsycInfo (APA)"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/psycinfo.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if "query_file" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                f"Source missing query_file search_parameter ({source.filename})"
            )

        if not Path(source.search_parameters["query_file"]).is_file():
            raise colrev_exceptions.InvalidQueryException(
                f"File does not exist: query_file {source.search_parameters['query_file']} "
                f"for ({source.filename})"
            )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

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
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        raise NotImplementedError

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of Psycinfo"""

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
            ris_entries = colrev.ops.load_utils_ris.load_ris_entries(
                filename=self.search_source.filename, ris_parser=PsycInfoRISParser
            )
            self.__ris_fixes(entries=ris_entries)
            records = colrev.ops.load_utils_ris.convert_to_records(ris_entries)

            load_operation.review_manager.dataset.save_records_dict_to_file(
                records=records,
                save_path=self.search_source.get_corresponding_bib_file(),
            )
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for PsycINFO"""

        return record
