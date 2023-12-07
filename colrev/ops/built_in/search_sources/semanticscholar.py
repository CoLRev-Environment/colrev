#! /usr/bin/env python
"""SearchSource: Semantic Scholar"""

from __future__ import annotations
import json
import typing

from semanticscholar import PaginatedResults

import semanticscholarui

from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from typing import TYPE_CHECKING

import requests as requests
# install zope package
import zope.interface
# install package dacite
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.doi_org as doi_connector
import colrev.ops.built_in.search_sources.utils as connector_utils
import colrev.record
import colrev.settings
import colrev.operation
import colrev.env.language_service
from colrev import settings
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import FieldValues

from semanticscholar import SemanticScholar

if TYPE_CHECKING:
    import colrev.ops.search
    import colrev.ops.prep


# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-many-lines

@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class SemanticScholarSearchSource(JsonSchemaMixin):
    """Semantic Scholar API"""

    __api_url = "https://api.semanticscholar.org/graph/v1/paper/search?"
    # API search limit is 100. Default is 10.
    # Can be added by using the __api_url+query="xxx"&__limit
    __limit = 100
    # Use offset to go through the entire list of found literature.
    # Simply add __limit to offset after one circle --> loop until everything is scouted
    # Ether use the thin gin ieee (ask Robert) or use the total of the json form
    # __api_url+query="xxx"&__limit&__offset
    __offset = 0

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.semanticscholar"

    docs_link = (
            "https://github.com/CoLRev-Environment/colrev/blob/main/"
            + "colrev/ops/built_in/search_sources/semanticscholar.md"
    )

    short_name = "S2"
    __s2_md_filename = Path("data/search/md_S2.bib")

    __availability_exception_message = (
        f"Semantic Scholar ({Colors.ORANGE}check https://status.api.semanticscholar.org/{Colors.END})")

    __s2_UI__ = semanticscholarui.SemanticScholarUI()
    __s2__ = SemanticScholar

    __search_return__ = None

    def __init__(
            self,
            *,
            source_operation: colrev.operation.Operation,
            settings: typing.Optional[dict] = None,
    ) -> None:

        self.review_manager = source_operation.review_manager
        #        if settings:
        #            # Semantic Scholar as a search source
        #            self.search_source = from_dict(
        #                data_class=self.settings_class, data=settings
        #            )
        #        else:
        #            # Semantic Scholar as a md-prep source
        #            s2_api_source_l = [
        #                s
        #                for s in self.review_manager.settings.sources
        #                if s.filename == self.__s2_api_filename
        #            ]
        #            if s2_api_source_l:
        #                self.search_source = s2_api_source_l[0]
        #            else:
        #                self.search_source = colrev.settings.SearchSource(
        #                    endpoint="colrev.semanticscholar",
        #                    filename=self.__S2_md_filename,
        #                    search_type=colrev.settings.SearchType.API,
        #                    search_parameters={},
        #                    comment="",
        #                )
        #            self.s2_lock = Lock()

        self.language_service = colrev.env.language_service.LanguageService()
        # self.etiquette = self.get_etiquette(review_manager=self.review_manager)
        # self.email = self.review_manager.get_committer()

        __search_return__ = ''

    def __query(self, **kwargs) -> typing.Iterator[dict]:  # type: ignore
        """Get records from Semantic Scholar based on a bibliographic query"""

        # Here don't use works or swagger_ui --> this is only for Crossref
        # We have to use semanticscholar (py) for that

        # works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        # crossref_query_return = works.query(**kwargs).sort("deposited").order("desc")
        # yield from crossref_query_return

    def __get_s2_parameters(self,
                            *,
                            rerun: bool
                            ) -> dict:
        """Get all parameters from the user, using the User Interface"""
        self.__s2_UI__.mainUI()
        search_subject = self.__s2_UI__.searchSubject
        params = self.__s2_UI__.searchParams

        dict_param = {
            search_subject: search_subject,
            params: params
        }

        return dict_param

    #        if ("\"total\": 0" in params):
    #            self.review_manager.logger.info("Nothing was found with the given search parameters: " + params)
    #            raise

    def keyword_search(self,
                       *,
                       params: dict,
                       rerun: bool
                       ) -> PaginatedResults:
        query = None
        year = None
        publication_types = None
        venue = None
        fields_of_study = None
        open_access_pdf = None
        limit = None

        for key, value in params.items():
            match key:
                case "query":
                    query = value
                case "year":
                    year = value
                case "publication_types":
                    publication_types = value
                case "venue":
                    venue = value
                case "fields_of_study":
                    fields_of_study = value
                case "open_access_pdf":
                    open_access_pdf = value
                case "limit":
                    limit = value

        record_return = self.__s2__.search_paper(query=query,
                                                 year=year,
                                                 publication_types=publication_types,
                                                 venue=venue,
                                                 fields_of_study=fields_of_study,
                                                 open_access_pdf=open_access_pdf,
                                                 limit=limit,
                                                 )
        return record_return

    def paper_search(self,
                     *,
                     params: dict,
                     rerun: bool
                     ) -> PaginatedResults:
        for key, value in params.items():
            if key == "paper_ids":
                record_return = self.__s2__.get_papers(value)
            elif key == "query":
                record_return = self.__s2__.search_paper(value)
            else:
                self.review_manager.logger.info(
                    "Search type \"Search for paper\" is not available with your parameters.\n"
                    + "Search parameter: "
                    + value
                )
        return record_return

    def author_search(self,
                      *,
                      params: dict,
                      rerun: bool
                      ) -> PaginatedResults:
        for key, value in params.items():
            if key == "author_ids":
                record_return = self.__s2__.get_authors(value)
            elif key == "queryList":
                record_return = self.__s2__.search_author(value)
            else:
                self.review_manager.logger.info(
                    "\nSearch type \"Search for author\" is not available with your parameters.\n"
                    + "Search parameter: "
                    + value
                )
        return record_return

    def __get_api_key(self) -> str:
        api_key = self.review_manager.environment_manager.get_settings_by_key(
            self.SETTINGS["api_key"]
        )
        if api_key is None: #or len(api_key) != 24:
            api_key = self.__s2_UI__.get_api_key() #input("Please enter api key: ")
            self.review_manager.environment_manager.update_registry(
                self.SETTINGS["api_key"], api_key
            )
        return api_key

    def run_search(
            self,
            *,
            rerun: bool
    ) -> None:
        """Run a search of Semantic Scholar"""

        # method call api key
        s2_api_key = self.__get_api_key()
        if s2_api_key is not None:
            self.__s2__(api_key=s2_api_key)

        # validate source

        s2_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun)
        )

        self.search_source.search_type = colrev.settings.SearchType.API

        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        try:
            # no full rerun
            # load the database (feed) --> __get_masterdata_record() and __get_masterdata()
            # or records = self.review_manager.dataset.load_records_dict()
            records = self.review_manager.dataset.load_records_dict()

            # get the search parameters from the user
            dict_param = self.__get_s2_parameters(rerun=rerun)
            __search_return__ = None
            try:
                # Open Semantic Scholar depending on the search subject  and look for search parameters
                match dict_param["search_subject"]:
                    case "keyword":
                        __search_return__ = self.keyword_search(params=dict_param["params"], rerun=rerun)
                    case "paper":
                        __search_return__ = self.paper_search(params=dict_param["params"], rerun=rerun)
                    case "author":
                        __search_return__ = self.author_search(params=dict_param["params"], rerun=rerun)
                    case _:
                        self.review_manager.logger.info(
                            "No search parameters were found."
                        )

                for item in __search_return__:
                    try:
                        retrieved_record_dict = connector_utils.json_to_record(item=item)
                        continue
                    except:
                        raise
            except:
                raise

            self.review_manager.dataset.save_records_dict(records=records)
        # pip install requests
        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self.__availability_exception_message
            ) from exc

    @classmethod
    def add_endpoint(
            cls,
            operation: colrev.ops.search.Search,
            params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint"""

        #    if list(params) == [Fields.ISSN]:
        #        search_type = colrev.settings.SearchType.TOC
        #    else:
        #        search_type = operation.select_search_type(
        #            search_types=cls.search_types, params=params
        #        )

        #    if search_type == colrev.settings.SearchType.API:
        #        if len(params) == 0:
        #            add_source = operation.add_api_source(endpoint=cls.endpoint)
        #            return add_source

        #        if Fields.URL in params:
        #            query = (
        #                params[Fields.URL]
        #                .replace("https://search.crossref.org/?q=", "")
        #                .replace("&from_ui=yes", "")
        #                .lstrip("+")
        #            )
        query = ''
        filename = operation.get_unique_filename(
            file_path_string=f"crossref_{query}"
        )
        add_source = colrev.settings.SearchSource(
            endpoint="colrev.crossref",
            filename=filename,
            search_type=colrev.settings.SearchType.API,
            search_parameters={"query": query},
            comment="",
        )
        return add_source

    raise NotImplementedError


