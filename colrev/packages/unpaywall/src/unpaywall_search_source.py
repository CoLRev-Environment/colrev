#! /usr/bin/env python
"""SearchSource: Unpaywall"""
from __future__ import annotations

import typing
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.exceptions as colrev_exceptions
from colrev.constants import SearchSourceHeuristicStatus, SearchType
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class UnpaywallSearchSource(JsonSchemaMixin):
    """Unpaywall Search Source"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    # source_identifier
    search_types = [SearchType.API]
    endpoint = "colrev.unpaywall"

    ci_supported: bool = False
    heuristic_status = SearchSourceHeuristicStatus.oni
    # docs_link

    short_name = "Unpaywall"
    # API_FIELDS
    # FIELD_MAPPING

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        """Not implemented"""
        pass

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Unpaywall"""
        # Not yet implemented
        result = {"confidence": 0.0}
        return result

    @classmethod
    def add_endpoint(
        cls, operation: colrev.ops.search.Search, params: dict
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        """Typically called for automated searches when running “colrev search -a SOURCE_NAME” to add search and query."""
        """Not implemented"""

        if len(params) == 0: #if no specific search sourch is given
            add_source = operation.add_db_source(search_source_cls=cls, params=params)
            return add_source

        if "URL" in params["url"]:
            url_parsed = urllib.parse.urlparse(params["url"])
            new_query = urllib.parse.parse_qs(url_parsed.query)
            search = new_query.get("search", [""])[0]
            start = new_query.get("start", ["0"])[0]
            rows = new_query.get("rows", ["2000"])[0]
            if ":" in search:
                search = UnpaywallSearchSource._search_split(search)
            filename = operation.get_unique_filename(file_path_string = "") #=f"eric_{search}"
            # code before this statement has do be adapted according to the data format of unpaywall 

            add_source = colrev.settings.SearchSource( #SearchSource metadata
                endpoint=cls.endpoint,
                filename=filename, #filename points to the file in which retrieved records are stored. It starts with data/search/
                search_type=SearchType.API,
                search_parameters={"query": search, "start": start, "rows": rows},
                comment="", #optional
            )
            return add_source

        raise colrev_exceptions.PackageParameterError(
            f"Cannot add UNPAYWALL endpoint with query {params}"
        )
        
    def search(self, rerun: bool) -> None:
        """Run a search of Unpaywall"""
        """Not implemented"""
        pass
    
    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        """Not implemented"""
        pass

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record
    
    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Unpaywall"""
        """Not implemented"""
        return record
    

if __name__ == "__main__":
    instance = UnpaywallSearchSource()
    instance.search()