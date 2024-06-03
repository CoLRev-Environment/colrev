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
from colrev.constants import Fields
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
        #"""Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        #"""Typically called for automated searches when running “colrev search -a SOURCE_NAME” to add search and query."""
        #"""Not implemented"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split("&"): # TODO figurte our what happens with the first part 	https://api.unpaywall.org/v2/search? 
                    key, value = item.split("=")
                    params_dict[key] = value
        
        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.API:
            if len(params) == 0: 
                add_source = operation.add_api_source(search_source_cls=cls, params=params)
                return add_source

            # TODO: delete one of the following "url", depending on the occurrence
            elif "https://api.unpaywall.org/v2/request?" or "https://api.unpaywall.org/v2/search?" in params_dict["url"]: # api.unpaywall.org/my/request?email=YOUR_EMAIL or [...].org/v2/search?query=:your_query[&is_oa=boolean][&page=integer]
                url_parsed = urllib.parse.urlparse(params_dict["url"])  
                new_query = urllib.parse.parse_qs(url_parsed.query)
                search_query = new_query.get("query", [""])[0]   
                is_oa = new_query.get("is_oa", [""])[0] 
                page = new_query.get("page", [""])[0] 
                # email = new_query.get("email", ["fillermail@thathastobechangedordeleted.net"])[0] # TODO: how to handle E-Mail? Save it? (I guess not, because it is not needed for the search itself)

                filename = operation.get_unique_filename(file_path_string=f"unpaywall_{search_query}")
                search_source = colrev.settings.SearchSource(
                    endpoint=cls.endpoint,
                    filename=filename, 
                    search_type=SearchType.API,
                    search_parameters={"query": search_query, "is_oa": is_oa, "page": page},
                    comment="",
                )
        elif search_type == SearchType.DB: 
            search_source = operation.create_db_source(
                search_source_cls=cls,
                params=params_dict,
            )

        else:
            raise colrev_exceptions.PackageParameterError(
                f"Cannot add UNPAYWALL endpoint with query {params}"
            )
        
        operation.add_source_and_search(search_source)
        
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