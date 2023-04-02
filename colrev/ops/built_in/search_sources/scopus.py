#! /usr/bin/env python
"""SearchSource: Scopus"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

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
class ScopusSearchSource(JsonSchemaMixin):
    """SearchSource for scopus"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "url"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = False
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "Scopus"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/scopus.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Scopus"""

        result = {"confidence": 0.0}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
            return result

        if "www.scopus.com" in data:
            if data.count("www.scopus.com") >= data.count("\n@"):
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

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if "query_file" not in source.search_parameters:
            print(
                f"Warning: Source missing query_file search_parameter ({source.filename})"
            )
        else:
            if not Path(source.search_parameters["query_file"]).is_file():
                raise colrev_exceptions.InvalidQueryException(
                    f"File does not exist: query_file {source.search_parameters['query_file']} "
                    f"for ({source.filename})"
                )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of Scopus"""

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
        """Load fixes for Scopus"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Scopus"""

        if "document_type" in record.data:
            if record.data["document_type"] == "Conference Paper":
                record.change_entrytype(new_entrytype="inproceedings")

            elif record.data["document_type"] == "Conference Review":
                record.change_entrytype(new_entrytype="proceedings")

            elif record.data["document_type"] == "Article":
                record.change_entrytype(new_entrytype="article")

            record.remove_field(key="document_type")

        if "Start_Page" in record.data and "End_Page" in record.data:
            if record.data["Start_Page"] != "nan" and record.data["End_Page"] != "nan":
                record.data["pages"] = (
                    record.data["Start_Page"] + "--" + record.data["End_Page"]
                )
                record.data["pages"] = record.data["pages"].replace(".0", "")
                record.remove_field(key="Start_Page")
                record.remove_field(key="End_Page")

        if "note" in record.data:
            if "cited By " in record.data["note"]:
                record.rename_field(key="note", new_key="cited_by")
                record.data["cited_by"] = record.data["cited_by"].replace(
                    "cited By ", ""
                )

        if "author" in record.data:
            record.data["author"] = record.data["author"].replace("; ", " and ")

        drop = ["source"]
        for field_to_drop in drop:
            record.remove_field(key=field_to_drop)

        return record


if __name__ == "__main__":
    pass
