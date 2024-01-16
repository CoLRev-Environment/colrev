#! /usr/bin/env python
"""SearchSource: Semantic Scholar"""
from __future__ import annotations

import typing
from copy import deepcopy
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
import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.operation
from colrev.ops.built_in.search_sources.semanticscholarui import Semanticscholar_ui
import colrev.ops.built_in.search_sources.utils as connector_utils
import colrev.record
import colrev.ops.load
import colrev.ops.load_utils_bib
import colrev.settings
from colrev.constants import Colors, Fields

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

    # Provide objects with classes
    __s2__: SemanticScholar
    __search_return__: PaginatedResults

    __limit = 100
    __offset = 0

    __api_url = "https://api.semanticscholar.org/graph/v1/paper/search?"

    endpoint = "colrev.semanticscholar"
    ci_supported: bool = True

    # SearchSourcePackageEndpointInterface constants
    docs_link = (
            "https://github.com/CoLRev-Environment/colrev/tree/main/"
            + "colrev/ops/built_in/search_sources/semanticscholar.md"
    )
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    search_types = [colrev.settings.SearchType.API]
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    short_name = "S2"
    source_identifier = Fields.DOI

    SETTINGS = {
        "api_key": "packages.search_source.colrev.semanticscholar.api_key",
    }

    __availability_exception_message = f"Semantic Scholar ({Colors.ORANGE}check https://status.api.semanticscholar.org/{Colors.END})"

    __s2_UI__ = Semanticscholar_ui()
    __s2_filename = Path("data/search/md_semscholar.bib")

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
                filename=self.__s2_filename,
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

        record_return = self.__s2__.search_paper(
            query=query,
            year=year,
            publication_types=publication_types,
            venue=venue,
            fields_of_study=fields_of_study,
            open_access_pdf=open_access_pdf,
        )

        self.review_manager.logger.info(
            '\n'
            + record_return.total
            + ', have been found.'
        )

        if record_return.total > self.__limit:
            self.review_manager.logger.info(
                '\nYou will only receive the first 100 not sorted results.'
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
            self.__s2__ = SemanticScholar(api_key=s2_api_key)
        else:
            self.__s2__ = SemanticScholar()

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
            search_subject = self.__s2_UI__.searchSubject
            params = self.__s2_UI__.searchParams

            # Get Semantic Scholar API depending on the search subject and look for search parameters
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
                    s2_feed.set_id(record_dict=retrieved_record_dict)
                    prev_record_dict_version = {}
                    if retrieved_record_dict[Fields.ID] in s2_feed.feed_records:
                        prev_record_dict_version = deepcopy(
                            s2_feed.feed_records[retrieved_record_dict[Fields.ID]]
                        )

                    retrieved_record = colrev.record.Record(data=retrieved_record_dict)
                    """ self.__prep_crossref_record(
                        record=retrieved_record, prep_main_record=False
                    )"""

                    added = s2_feed.add_record(record=retrieved_record)

                    if added:
                        self.review_manager.logger.info(
                            " retrieve " + retrieved_record.data[Fields.DOI]
                        )
                    else:
                        s2_feed.update_existing_record(
                            records=records,
                            record_dict=retrieved_record.data,
                            prev_record_dict_version=prev_record_dict_version,
                            source=self.search_source,
                            update_time_variant_fields=rerun,
                        )

                    # Note : only retrieve/update the latest deposits (unless in rerun mode)
                    if not added:
                        # problem: some publishers don't necessarily
                        # deposit papers chronologically
                        self.review_manager.logger.debug("Break condition")
                        break
                except (
                    colrev_exceptions.RecordNotParsableException,
                    colrev_exceptions.NotFeedIdentifiableException,
                ):
                    pass
        except KeyError as exc:
            print(exc)
            # KeyError  # error in semanticscholar package:
            # if len(result['message']['items']) == 0:
            # KeyError: 'items'

        s2_feed.print_post_run_search_infos(records=records)
        s2_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        # get search parameters from the user interface
        cls.__s2_UI__.main_ui()
        search_params = cls.__s2_UI__.searchParams

        filename = operation.get_unique_filename(
            file_path_string=f"semanticscholar_{search_params}",
        )

        add_source = colrev.settings.SearchSource(
            endpoint="colrev.semanticscholar",
            filename=filename,
            search_type=colrev.settings.SearchType.API,
            search_parameters=params,
            comment="",
        )
        return add_source

    # Aktuell noch von crossref - muss noch verändert werden
    def get_masterdata(
            self,
            prep_operation: colrev.ops.prep.Prep,
            record: colrev.record.Record,
            save_feed: bool = True,
            timeout: int = 30,
    ) -> colrev.record.Record:
        """Out of scope"""
        pass


    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Semantic Scholar"""
        result = {"confidence": 0.0}
        return result

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

    # Aktuell noch von crossref - muss noch verändert werden
    def prepare(
            self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.PrepRecord:
        """Source-specific preparation for Crossref"""
        pass


if __name__ == "__main__":
    test = SemanticScholarSearchSource
    test.run_search(rerun=False)
