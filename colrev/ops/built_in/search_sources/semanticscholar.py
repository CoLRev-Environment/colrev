#! /usr/bin/env python
"""SearchSource: Semantic Scholar"""

from __future__ import annotations
import json
import typing

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

    def __query(self, **kwargs) -> typing.Iterator[dict]:  # type: ignore
        """Get records from Semantic Scholar based on a bibliographic query"""

        # Here don't use works or swagger_ui --> this is only for Crossref
        # We have to use semanticscholar (py) for that

        #works = Works(etiquette=self.etiquette)
        # use facets:
        # https://api.crossref.org/swagger-ui/index.html#/Works/get_works

        #crossref_query_return = works.query(**kwargs).sort("deposited").order("desc")
        #yield from crossref_query_return

    def __get_s2_query_return(self, *, rerun: bool) -> typing.Iterator[dict]:
        # Here you potentially get the query parameters
        params = self.search_source.search_parameters

        if not ("query" in params):
            # Raising an exception
            # but maybe check that earlier, because without query there is no json with the url
            raise

        if ("\"total\": 0" in params):
            self.review_manager.logger.info("Nothing was found with the given search parameters: " + params)
            raise

        s2_query = {"bibliographic": params["query"].replace(" ", "+")}





    def run_search(
            self,
            *,
            rerun: bool
    ) -> None:
        """Run a search of Semantic Scholar"""
        # validate
        try:
            if rerun:
                self.review_manager.logger.info(
                    "Performing a search of the full history (may take time)"
                )

            # no full rerun
            # load the database (feed) --> __get_masterdata_record() and __get_masterdata()
            # or records = self.review_manager.dataset.load_records_dict()
            records = self.review_manager.dataset.load_records_dict()

            try:
                for item in self.__get_s2_query_return(rerun=rerun):
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
