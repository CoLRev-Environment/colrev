#! /usr/bin/env python
"""SearchSource: Semantic Scholar"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from typing import TYPE_CHECKING

import requests as requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from semanticscholar import SemanticScholar
from semanticscholar.PaginatedResults import PaginatedResults

import colrev.env.language_service
import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.ops.built_in.search_sources.semanticscholarui
import colrev.ops.built_in.search_sources.utils as connector_utils
import colrev.record
import colrev.settings
from colrev.constants import Colors

# install zope package
# install package dacite

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

    s2: SemanticScholar

    __api_url = "https://api.semanticscholar.org/graph/v1/paper/search?"
    __limit = 100
    __offset = 0

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.semanticscholar"

    search_types = [
        colrev.settings.SearchType.API,
    ]

    ci_supported: bool = True

    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/semanticscholar.md"
    )

    SETTINGS = {
        "api_key": "packages.search_source.colrev.semanticscholar.api_key",
    }

    short_name = "S2"
    __s2_md_filename = Path("data/search/md_S2.bib")

    __availability_exception_message = f"Semantic Scholar ({Colors.ORANGE}check https://status.api.semanticscholar.org/{Colors.END})"

    __s2_UI__ = (
        colrev.ops.built_in.search_sources.semanticscholarui.Semanticscholar_ui()
    )

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # Semantic Scholar as a search source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint="colrev.semanticscholar",
                filename=self.__S2_md_filename,
                search_type=colrev.settings.SearchType.API,
                search_parameters={},
                comment="",
            )
            self.s2_lock = Lock()

        self.language_service = colrev.env.language_service.LanguageService()
        __search_return__ = None

    def __get_s2_parameters(self, *, rerun: bool) -> None:
        """Get all parameters from the user, using the User Interface"""
        self.__s2_UI__.main_ui()

    def keyword_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
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
                    if not value == "":
                        limit = int(value)

        record_return = self.__s2__.search_paper(
            query=query,
            year=year,
            publication_types=publication_types,
            venue=venue,
            fields_of_study=fields_of_study,
            open_access_pdf=open_access_pdf,
            limit=limit,
        )
        return record_return

    def paper_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        for key, value in params.items():
            if key == "paper_ids":
                record_return = self.__s2__.get_papers(value)
            elif key == "query":
                record_return = self.__s2__.search_paper(value)
            else:
                self.review_manager.logger.info(
                    'Search type "Search for paper" is not available with your parameters.\n'
                    + "Search parameter: "
                    + value
                )
        return record_return

    def author_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        for key, value in params.items():
            if key == "author_ids":
                record_return = self.__s2__.get_authors(value)
            elif key == "queryList":
                record_return = self.__s2__.search_author(value)
            else:
                self.review_manager.logger.info(
                    '\nSearch type "Search for author" is not available with your parameters.\n'
                    + "Search parameter: "
                    + value
                )
        return record_return

    def __get_api_key(self) -> str:
        api_key = self.review_manager.environment_manager.get_settings_by_key(
            self.SETTINGS["api_key"]
        )
        if api_key is None:
            api_key = self.__s2_UI__.get_api_key()
            self.review_manager.environment_manager.update_registry(
                self.SETTINGS["api_key"], api_key
            )
        return api_key

    def run_search(self, *, rerun: bool) -> None:
        """Run a search of Semantic Scholar"""

        # get the api key
        s2_api_key = self.__get_api_key()
        if s2_api_key:
            self.s2 = self.__s2__(api_key=s2_api_key)
        else:
            self.s2 = self.__s2__()

        # validate source

        # load file because the object is not shared between processes
        s2_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        try:
            records = self.review_manager.dataset.load_records_dict()

            # get the search parameters from the user
            # self.__get_s2_parameters(rerun=rerun)
            search_subject = self.__s2_UI__.searchSubject
            params = self.__s2_UI__.searchParams

            try:
                # Open Semantic Scholar depending on the search subject  and look for search parameters
                match search_subject:
                    case "keyword":
                        __search_return__ = self.keyword_search(
                            params=params, rerun=rerun
                        )
                    case "paper":
                        __search_return__ = self.paper_search(
                            params=params, rerun=rerun
                        )
                    case "author":
                        __search_return__ = self.author_search(
                            params=params["params"], rerun=rerun
                        )
                    case _:
                        self.review_manager.logger.info(
                            "No search parameters were found."
                        )

                for item in __search_return__:
                    try:
                        retrieved_record_dict = connector_utils.json_to_record(
                            item=item
                        )
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
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Semantic Scholar"""
        result = {"confidence": 0.0}
        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        # get search parameters from the user interface
        cls.__s2_UI__.main_ui()
        params = cls.__s2_UI__.searchParams

        if len(params) == 0:
            add_source = operation.add_api_source(endpoint=cls.endpoint)
            return add_source

        filename = operation.get_unique_filename(file_path_string="semanticscholar_")
        add_source = colrev.settings.SearchSource(
            endpoint="colrev.semanticscholar",
            filename=filename,
            search_type=colrev.settings.SearchType.API,
            search_parameters=params,
            comment="",
        )
        return add_source


if __name__ == "__main__":
    test = SemanticScholarSearchSource
    test.run_search(rerun=False)
