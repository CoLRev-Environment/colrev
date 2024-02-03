#! /usr/bin/env python
"""SearchSource: Semantic Scholar"""
from __future__ import annotations

import typing
from copy import deepcopy
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from semanticscholar import SemanticScholar
from semanticscholar import SemanticScholarException
from semanticscholar.PaginatedResults import PaginatedResults

import colrev.constants
import colrev.env.environment_manager
import colrev.env.language_service
import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.ops.built_in.search_sources.semanticscholar_utils as connector_utils
import colrev.ops.load
import colrev.ops.load_utils_bib
import colrev.record
import colrev.settings
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.ops.built_in.search_sources.semanticscholar_ui import SemanticScholarUI

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
    """Semantic Scholar API Search Source"""

    # Provide objects with classes
    __s2__: SemanticScholar
    __search_return__: PaginatedResults

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
    source_identifier = Fields.SEMANTIC_SCHOLAR_ID

    SETTINGS = {
        "api_key": "packages.search_source.colrev.semanticscholar.api_key",
    }

    __availability_exception_message = (
        f"Semantic Scholar ({Colors.ORANGE}check "
        f"https://status.api.semanticscholar.org/{Colors.END})"
    )

    __s2_UI__ = SemanticScholarUI()
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

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check the availability of the Semantic Scholar API"""

        try:
            # pylint: disable=duplicate-code
            test_doi = "10.17705/1CAIS.04607"
            test_record = {
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                + "Validation of a new Typology in the IS Field",
                "url": "https://www.semanticscholar.org/paper"
                "/b639a05d936dfd519fe4098edc95b5680b7ec7ec",
            }

            returned_record = self.__s2__.get_paper(paper_id=test_doi)

            if 0 != len(returned_record):
                assert returned_record[Fields.TITLE] == test_record[Fields.TITLE]
                assert returned_record[Fields.URL] == test_record[Fields.URL]
            else:
                if not source_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException(
                        self.__availability_exception_message
                    )
        except (requests.exceptions.RequestException, IndexError) as exc:
            print(exc)
            if not source_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    self.__availability_exception_message
                ) from exc

    def __get_semantic_scholar_api(
        self, *, params: dict, subject: str, rerun: bool
    ) -> PaginatedResults:
        """Get Semantic Scholar API depending on
        the search subject and look for search parameters"""
        if subject == "keyword":
            __search_return__ = self.keyword_search(params=params, rerun=rerun)
        elif subject == "paper":
            __search_return__ = self.paper_search(params=params, rerun=rerun)
        elif subject == "author":
            __search_return__ = self.author_search(params=params, rerun=rerun)
        else:
            self.review_manager.logger.info("No search parameters were found.")

        return __search_return__

    def keyword_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        """Prepare search parameters and conduct full keyword search with the python client"""

        query = None
        year = None
        venue = None
        fields_of_study = None
        open_access_pdf = None

        for key, value in params.items():
            if key == "query":
                query = value
            elif key == "year":
                year = value
            elif key == "venue":
                venue = value
            elif key == "fields_of_study":
                fields_of_study = value
            elif key == "open_access_pdf":
                open_access_pdf = value

        try:
            record_return = self.__s2__.search_paper(
                query=query,
                year=year,
                publication_types=None,
                venue=venue,
                fields_of_study=fields_of_study,
                open_access_pdf=open_access_pdf,
            )
        except (
            SemanticScholarException.SemanticScholarException,
            SemanticScholarException.BadQueryParametersException,
        ) as exc:
            self.review_manager.logger.error(
                "Error: Something went wrong during the search with the Python Client."
                + " This program will close."
            )
            print(exc)
            raise colrev_exceptions.ServiceNotAvailableException(exc)

        self.review_manager.logger.info(
            str(record_return.total) + " records have been found.\n"
        )

        if record_return.total == 0:
            self.review_manager.logger.info(
                "Search aborted because no records were found. This program will close."
            )
            raise colrev_exceptions.ServiceNotAvailableException(
                "No records were found."
            )

        return record_return

    def paper_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        """Method to conduct an API search of SemanticScholar with a List of Paper IDs"""

        if "paper_ids" in params:
            try:
                record_return = self.__s2__.get_papers(params.get("paper_ids"))
            except (
                SemanticScholarException.SemanticScholarException,
                SemanticScholarException.BadQueryParametersException,
            ) as exc:
                self.review_manager.logger.error(
                    "Error: Something went wrong during the search with the Python Client."
                    + " This program will close."
                )
                print(exc)
                raise colrev_exceptions.ServiceNotAvailableException(exc)
        else:
            self.review_manager.logger.error(
                'Error: Search type "Search for paper" is not available with your parameters.\n'
                + "Search parameter: "
                + str(params.get("paper_ids"))
            )
            raise colrev_exceptions.ServiceNotAvailableException(
                "Search parameter error."
            )
        return record_return

    def author_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        """Method to conduct an API search of SemanticScholar with a List of Author IDs"""

        if "author_ids" in params:
            try:
                record_return = self.__s2__.get_authors(params.get("author_ids"))
            except (
                SemanticScholarException.SemanticScholarException,
                SemanticScholarException.BadQueryParametersException,
            ) as exc:
                self.review_manager.logger.error(
                    "Error: Something went wrong during the search with the Python Client."
                    + " This program will close."
                )
                print(exc)
                raise colrev_exceptions.ServiceNotAvailableException(exc)
        else:
            self.review_manager.logger.error(
                '\nError: Search type "Search for author" is not available with your parameters.\n'
                + "Search parameter: "
                + str(params.get("author_ids"))
            )
            raise colrev_exceptions.ServiceNotAvailableException(
                "Search parameter error."
            )
        return record_return

    def __get_api_key(self) -> str:
        """Method to request an API key from the settings file - or, if empty, from user input"""
        api_key = self.review_manager.environment_manager.get_settings_by_key(
            self.SETTINGS["api_key"]
        )

        if api_key:
            api_key = self.__s2_UI__.get_api_key(api_key)
        else:
            api_key = self.__s2_UI__.get_api_key()

        if api_key:
            self.review_manager.environment_manager.update_registry(
                self.SETTINGS["api_key"], api_key
            )
        else:
            self.review_manager.environment_manager.update_registry(
                self.SETTINGS["api_key"], ""
            )

        return api_key

    def run_search(self, rerun: bool) -> None:
        """Run a search of Semantic Scholar"""

        # get the api key
        s2_api_key = self.__get_api_key()
        if s2_api_key:
            self.__s2__ = SemanticScholar(api_key=s2_api_key)
        else:
            self.__s2__ = SemanticScholar()

        # load file because the object is not shared between processes
        s2_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )
        # rerun not implemented yet
        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )
        records = self.review_manager.dataset.load_records_dict()
        try:
            params = self.search_source.search_parameters
            search_subject = params.get("search_subject")
            del params["search_subject"]

            __search_return__ = self.__get_semantic_scholar_api(
                params=params, subject=search_subject, rerun=rerun
            )

        except SemanticScholarException.BadQueryParametersException as exc:
            self.review_manager.logger.error(
                "Error: Invalid Search Parameters. The Program will close."
            )
            print(exc)
            raise colrev_exceptions.ServiceNotAvailableException(exc)
            # KeyError  # error in semanticscholar package:
        except (KeyError, PermissionError) as exc:
            self.review_manager.logger.error(
                "Error: Search could not be conducted. Please check your Parameters and API key."
            )
            print(exc)
            raise colrev_exceptions.ServiceNotAvailableException("No valid API key.")

        try:
            for item in __search_return__:
                retrieved_record_dict = connector_utils.s2_dict_to_record(item=item)

                s2_feed.set_id(record_dict=retrieved_record_dict)
                prev_record_dict_version = {}

                if (
                    retrieved_record_dict[self.source_identifier]
                    in s2_feed.feed_records
                ):
                    prev_record_dict_version = deepcopy(
                        s2_feed.feed_records[
                            retrieved_record_dict[self.source_identifier]
                        ]
                    )

                retrieved_record_dict[self.source_identifier] = retrieved_record_dict[
                    self.source_identifier
                ]
                retrieved_record = colrev.record.Record(data=retrieved_record_dict)

                added = s2_feed.add_record(record=retrieved_record)

                if added:
                    if self.__s2_UI__.search_subject == "author":
                        self.review_manager.logger.info(
                            "retrieve "
                            + retrieved_record.data[Fields.SEMANTIC_SCHOLAR_ID]
                        )
                    else:
                        self.review_manager.logger.info(
                            "retrieve "
                            + retrieved_record.data[Fields.SEMANTIC_SCHOLAR_ID]
                        )
                else:
                    s2_feed.update_existing_record(
                        records=records,
                        record_dict=retrieved_record.data,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )
        except (
            colrev_exceptions.RecordNotParsableException,
            colrev_exceptions.NotFeedIdentifiableException,
        ) as exc:
            self.review_manager.logger.error(
                "Error: Retrieved records were not parsable into feed and result file."
            )
            print(exc)

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
        search_subject = cls.__s2_UI__.search_subject
        search_params = cls.__s2_UI__.search_params

        search_params["search_subject"] = search_subject

        # decrease probability to reach linux file name length limit
        # by only using three parameters for result file
        short_search_params_key_list = [
            "query",
            "paper_ids",
            "author_ids",
            "year",
            "open_access_pdf",
        ]
        short_search_params = {}

        if search_params:
            for key, value in search_params.items():
                if key in short_search_params_key_list:
                    short_search_params[key] = value

        if "query" in short_search_params:
            if len(short_search_params["query"]) > 50:
                short_search_params["query"] = short_search_params["query"][0:50]

        filename = operation.get_unique_filename(file_path_string="semanticscholar")

        add_source = colrev.settings.SearchSource(
            endpoint="colrev.semanticscholar",
            filename=filename,
            search_type=colrev.settings.SearchType.API,
            search_parameters=search_params,
            comment="",
        )
        return add_source

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 30,
    ) -> colrev.record.Record:
        """Retrieve master data from Semantic Scholar"""
        # Not yet implemented

        return record

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Semantic Scholar"""
        # Not yet implemented

        result = {"confidence": 0.0}

        return result

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        # Not yet implemented

        if self.search_source.filename.suffix == ".bib":
            bib_loader = colrev.ops.load_utils_bib.BIBLoader(
                load_operation=load_operation, source=self.search_source
            )
            records = bib_loader.load_bib_file()

            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.PrepRecord:
        """Source-specific preparation for Semantic Scholar"""
        # Not yet implemented
        return record
