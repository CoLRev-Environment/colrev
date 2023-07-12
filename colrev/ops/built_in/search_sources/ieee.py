#! /usr/bin/env python
"""SearchSource: IEEEXplore"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record
import colrev.ops.prep
import colrev.env.package_manager

import colrev.ops.built_in.search_sources.xploreapi

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class IEEEXploreSearchSource(JsonSchemaMixin):
    """SearchSource for IEEEXplore"""

    flag=True
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "ID"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    short_name = "IEEE Xplore"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/ieee.md"
    )
    SETTINGS= {
        "api_key": "packages.search_source.colrev.ieee.api_key",
    }

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
       

        if settings:
            self.search_source = from_dict(data_class=self.settings_class, data=settings)
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint="colrev.ieee",
                filename=Path("data/search/ieee.bib"),
                search_type=colrev.settings.SearchType.OTHER,
                search_parameters={},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
    # For run_search, a Python SDK would be available:
    # https://developer.ieee.org/Python_Software_Development_Kit

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        
        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for IEEEXplore"""

        result = {"confidence": 0.1}

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        if "https://ieeexploreapi.ieee.org/api/v1/search/articles?" in query:
            query = (query.replace("https://ieeexploreapi.ieee.org/api/v1/search/articles?", "").lstrip("&")
            )            

            parameter_pairs = query.split("&")
            search_parameters = {}
            for parameter in parameter_pairs:
                key, value = parameter.split("=")
                search_parameters[key] = value

            last_value = list(search_parameters.values())[-1]

            filename = search_operation.get_unique_filename(
                file_path_string=f"ieee_{last_value}"
            )

            add_source = colrev.settings.SearchSource(
                endpoint="colrev.ieee",
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters=search_parameters,
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source
          
        raise NotImplementedError

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of IEEEXplore"""

        ieee_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        ) 
        api_key = self.review_manager.environment_manager.get_settings_by_key(self.SETTINGS["api_key"])
        if api_key is None or len(api_key) != 24:
            api_key = input("Please enter api key: ")
            self.review_manager.environment_manager.update_registry(self.SETTINGS["api_key"], api_key)

        key=self.review_manager.environment_manager.get_settings_by_key (self.SETTINGS["api_key"])
       
        prev_record_dict_version = {}

        query = colrev.ops.built_in.search_sources.xploreapi.XPLORE(key)
        query.dataType('json')
        query.dataFormat('object')
        query.maximumResults(50000)
        query.usingOpenAccess = False

        parameter_methods = {}
        parameter_methods["article_number"] = query.articleNumber
        parameter_methods["doi"] = query.doi
        parameter_methods["author"] = query.authorText
        parameter_methods["isbn"] = query.isbn
        parameter_methods["issn"] = query.issn
        parameter_methods["publication_year"] = query.publicationYear
        parameter_methods["queryText"] = query.queryText
        parameter_methods["parameter"] = query.queryText

        parameters = self.search_source.search_parameters
        for key, value in parameters.items():
            if key in parameter_methods:
                method = parameter_methods[key]
                method(value)

        response = query.callAPI()
        records = search_operation.review_manager.dataset.load_records_dict()
        articles = response["articles"]

        for article in articles:
            article_id = article['article_number']
            if article_id not in records:
                record_dict = self.__create_record_dict(article)
                updated_record_dict = self.__update_record_fields(record_dict)
                record = colrev.record.Record(data=updated_record_dict)
                added = ieee_feed.add_record(record=record)

                if added:
                    search_operation.review_manager.logger.info(
                        " retrieve " + record.data["ID"]
                    )
                    ieee_feed.nr_added += 1
                else:
                    changed = search_operation.update_existing_record(
                        records=records,
                        record_dict=record.data,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )
                    if changed:
                        search_operation.review_manager.logger.info(
                                " update " + record.data["ID"]
                        )
                        ieee_feed.nr_changed += 1
                        
        ieee_feed.save_feed_file()       
        search_operation.review_manager.dataset.save_records_dict(records=records)
        search_operation.review_manager.dataset.add_record_changes()
    
    def __create_record_dict(self, article):
        record_dict = {'ID': article['article_number']}

        api_fields = ['abstract', 'abstract_url', 'author_url', 'accessType', 
                      'article_number', 'author_order', 'author_terms', 'authors',
                      'affiliation', 'citing_paper_count', 'citing_patent_count', 'conference_dates', 
                      'conference_location', 'content_type','doi', 'publisher', 
                      'pubtype', 'd-year', 'end_page', 'facet', 
                      'full_name', 'html_url', 'index_terms', 'ieee_terms', 
                      'is_number', 'isbn', 'issn', 'issue', 
                      'pdf_url', 'publication_date', 'publication_year', 'publication_number', 
                      'publication_title', 'rank', 'standard_number', 'standard_status', 
                      'start_page', 'title', 'totalfound', 'totalsearched', 
                      'volume', 'insert_date']

        for field in api_fields:
            field_value = article.get(field)
            record_dict['ENTRYTYPE'] = 'article'
            if field_value is not None:
                if field == 'content_type':
                    record_dict['ENTRYTYPE'] = field_value
                else:
                    record_dict[field] = str(field_value)

        return record_dict

    def __update_record_fields(self,
        record_dict: dict, 
    ) -> dict:
        if "publication_year" in record_dict:
            record_dict["year"] = record_dict.pop("publication_year")
        if "content_type" in record_dict:
            record_dict["howpublished"] = record_dict.pop("content_type")
        if "publication_title" in record_dict:
            record_dict["journal"] = record_dict.pop("publication_title")
        if "author_url" in record_dict:
            record_dict["address"] = record_dict.pop("author_url")
        return record_dict
   

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
        """Load fixes for IEEEXplore"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for IEEEXplore"""

        return record