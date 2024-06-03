#! /usr/bin/env python
"""SearchSource: Unpaywall"""
from __future__ import annotations

from multiprocessing import Lock
import typing
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from dacite import from_dict
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
        self.review_manager = source_operation.review_manager
        if settings:
            # Unpaywall as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint=self.endpoint,
                filename=Path("data/search/unpaywall.bib"),
                search_type=SearchType.API,
                search_parameters={},
                comment="",
            )

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

        if len(params) == 0: #if no specific search source is given
            add_source = operation.add_api_source(search_source_cls=cls, params=params)
            return add_source

        # TODO: delete one of the following "url", depending on the occurrence
        if "URL" in params["url"] or "url" in params["url"]: # api.unpaywall.org/my/request?email=YOUR_EMAIL or [...].org/v2/search?query=:your_query[&is_oa=boolean][&page=integer]
            query = params["query"]
            is_oa = params.get("is_oa", [""])[0]
            page = params.get("page", [""])[0] # TODO: how to handle E-Mail?
            # email = params.get("email", None)

            if query: # checks if a search query is given
                # creates a SearchSource instance for Unpaywall search
                add_source = colrev.settings.SearchSource(
                    endpoint=cls.endpoint,
                    filename="",  # TODO: edit filename
                    search_type=SearchType.API,
                    search_parameters={"query": query, "is_oa": is_oa, "page": page},
                    comment="Searching Unpaywall API based on query parameters.",
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

        if self.search_source.filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                logger=self.review_manager.logger,
            )
            return records

        raise NotImplementedError

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