#! /usr/bin/env python
"""SearchSource: Semantic Scholar"""
from __future__ import annotations

import logging
import typing
from multiprocessing import Lock
from pathlib import Path

from pydantic import Field
from semanticscholar import SemanticScholarException
from semanticscholar.PaginatedResults import PaginatedResults

import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.search_file
import colrev.utils
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.semanticscholar.src import record_transformer
from colrev.packages.semanticscholar.src import semanticscholar_api
from colrev.packages.semanticscholar.src.semanticscholar_ui import SemanticScholarUI

if typing.TYPE_CHECKING:  # pragma: no cover

    import colrev.ops.prep


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class SemanticScholarSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Semantic Scholar API Search Source"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    # Provide objects with classes
    _search_return: PaginatedResults
    api: semanticscholar_api.SemanticScholarAPI

    endpoint = "colrev.semanticscholar"
    ci_supported: bool = Field(default=True)

    # SearchSourcePackageBaseClass constants
    heuristic_status = SearchSourceHeuristicStatus.oni
    search_types = [SearchType.API]

    source_identifier = Fields.SEMANTIC_SCHOLAR_ID

    SETTINGS = {
        "api_key": "packages.search_source.colrev.semanticscholar.api_key",
    }

    _availability_exception_message = (
        f"Semantic Scholar ({Colors.ORANGE}check "
        f"https://status.api.semanticscholar.org/{Colors.END})"
    )

    _s2_UI = SemanticScholarUI()
    _s2_filename = Path("data/search/md_semscholar.bib")

    def __init__(
        self,
        *,
        search_file: typing.Optional[colrev.search_file.ExtendedSearchFile] = None,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode

        if search_file:
            # Semantic Scholar as a search source
            self.search_source = search_file
        else:
            self.search_source = colrev.search_file.ExtendedSearchFile(
                version=self.CURRENT_SYNTAX_VERSION,
                platform="colrev.semanticscholar",
                search_results_path=self._s2_filename,
                search_type=SearchType.API,
                search_string="",
                comment="",
            )
            self.s2_lock = Lock()
        self.api = semanticscholar_api.SemanticScholarAPI()

    def check_availability(self) -> None:
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

            returned_record = self.api.get_paper(paper_id=test_doi)

            if 0 != len(returned_record):
                assert returned_record[Fields.TITLE] == test_record[Fields.TITLE]
                assert returned_record[Fields.URL] == test_record[Fields.URL]
            else:
                raise colrev_exceptions.ServiceNotAvailableException(
                    self._availability_exception_message
                )
        except (
            semanticscholar_api.SemanticScholarAPIError,
            IndexError,
        ) as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    def _get_semantic_scholar_api(
        self, *, params: dict, rerun: bool
    ) -> PaginatedResults:
        """Get Semantic Scholar API depending on
        the search subject and look for search parameters"""
        subject = params.pop("search_subject")
        if subject == "keyword":
            _search_return = self.keyword_search(params=params, rerun=rerun)
        elif subject == "paper":
            _search_return = self.paper_search(params=params, rerun=rerun)
        elif subject == "author":
            _search_return = self.author_search(params=params, rerun=rerun)
        else:
            self.logger.info("No search parameters were found.")
            raise NotImplementedError

        return _search_return

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
            record_return = self.api.search_paper(
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
            semanticscholar_api.SemanticScholarAPIError,
        ) as exc:
            self.logger.error(
                "Error: Something went wrong during the search with the Python Client."
                + " This program will close."
            )
            print(exc)
            raise colrev_exceptions.ServiceNotAvailableException(
                dep=self.endpoint
            ) from exc

        self.logger.info("%s records have been found.\n", record_return.total)

        if record_return.total == 0:
            self.logger.info(
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
                record_return = self.api.get_papers(params["paper_ids"])
            except (
                SemanticScholarException.SemanticScholarException,
                SemanticScholarException.BadQueryParametersException,
                semanticscholar_api.SemanticScholarAPIError,
            ) as exc:
                self.logger.error(
                    "Error: Something went wrong during the search with the Python Client."
                    + " This program will close."
                )
                print(exc)
                raise colrev_exceptions.ServiceNotAvailableException(
                    dep=self.endpoint
                ) from exc
        else:
            self.logger.error(
                'Error: Search type "Search for paper"'
                + " is not available with your parameters.\nSearch parameter: %s",
                params.get("paper_ids"),
            )
            raise colrev_exceptions.ServiceNotAvailableException(
                "Search parameter error."
            )
        return record_return

    def author_search(self, *, params: dict, rerun: bool) -> PaginatedResults:
        """Method to conduct an API search of SemanticScholar with a List of Author IDs"""

        if "author_ids" in params:
            try:
                record_return = self.api.get_authors(params["author_ids"])
            except (
                SemanticScholarException.SemanticScholarException,
                SemanticScholarException.BadQueryParametersException,
                semanticscholar_api.SemanticScholarAPIError,
            ) as exc:
                self.logger.error(
                    "Error: Something went wrong during the search with the Python Client."
                    + " This program will close."
                )
                print(exc)
                raise colrev_exceptions.ServiceNotAvailableException(
                    dep=self.endpoint
                ) from exc
        else:
            self.logger.error(
                '\nError: Search type "Search for author"'
                + " is not available with your parameters.\nSearch parameter: %s",
                params.get("author_ids"),
            )
            raise colrev_exceptions.ServiceNotAvailableException(
                "Search parameter error."
            )
        return record_return

    def _get_api_key(self) -> str:
        """Method to request an API key from the settings file - or, if empty, from user input"""
        api_key = (
            colrev.env.environment_manager.EnvironmentManager().get_settings_by_key(
                self.SETTINGS["api_key"]
            )
        )

        if api_key:
            api_key = self._s2_UI.get_api_key(api_key)
        else:
            api_key = self._s2_UI.get_api_key()

        if api_key:
            colrev.env.environment_manager.EnvironmentManager().update_registry(
                self.SETTINGS["api_key"], api_key
            )
        else:
            colrev.env.environment_manager.EnvironmentManager().update_registry(
                self.SETTINGS["api_key"], ""
            )

        return api_key

    def search(self, rerun: bool) -> None:
        """Run a search of Semantic Scholar"""

        # get the api key
        s2_api_key = self._get_api_key()
        if s2_api_key:
            self.api = semanticscholar_api.SemanticScholarAPI(api_key=s2_api_key)
        else:
            self.api = semanticscholar_api.SemanticScholarAPI()

        # load file because the object is not shared between processes
        s2_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )
        # rerun not implemented yet
        if rerun:
            self.logger.info("Performing a search of the full history (may take time)")
        try:
            params = self.search_source.search_parameters
            _search_return = self._get_semantic_scholar_api(params=params, rerun=rerun)

        except SemanticScholarException.BadQueryParametersException as exc:
            self.logger.error(
                "Error: Invalid Search Parameters. The Program will close."
            )
            print(exc)
            raise colrev_exceptions.ServiceNotAvailableException(exc)
            # KeyError  # error in semanticscholar package:
        except (KeyError, PermissionError) as exc:
            self.logger.error(
                "Error: Search could not be conducted. Please check your Parameters and API key."
            )
            print(exc)
            raise colrev_exceptions.ServiceNotAvailableException("No valid API key.")
        except semanticscholar_api.SemanticScholarAPIError as exc:
            self.logger.error(
                "Error: Something went wrong when communicating with Semantic Scholar."
            )
            print(exc)
            raise colrev_exceptions.ServiceNotAvailableException(
                dep=self.endpoint
            ) from exc

        try:
            for item in _search_return:
                retrieved_record = record_transformer.dict_to_record(item=item)
                s2_feed.add_update_record(retrieved_record)

        except (
            colrev_exceptions.RecordNotParsableException,
            colrev_exceptions.NotFeedIdentifiableException,
        ) as exc:
            self.logger.error(
                "Error: Retrieved records were not parsable into feed and result file."
            )
            print(exc)

        s2_feed.save()

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        # get search parameters from the user interface
        cls._s2_UI.main_ui()
        search_subject = cls._s2_UI.search_subject
        search_params = cls._s2_UI.search_params

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

        filename = colrev.utils.get_unique_filename(
            base_path=path,
            file_path_string="semanticscholar",
        )

        search_source = colrev.search_file.ExtendedSearchFile(
            version=cls.CURRENT_SYNTAX_VERSION,
            platform="colrev.semanticscholar",
            search_results_path=filename,
            search_type=SearchType.API,
            search_string="",
            search_parameters=search_params,
            comment="",
        )
        return search_source

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 30,
    ) -> colrev.record.record.Record:
        """Retrieve master data from Semantic Scholar"""
        # Not yet implemented
        return record

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Semantic Scholar"""
        # Not yet implemented

        result = {"confidence": 0.0}

        return result

    def load(self) -> dict:
        """Load the records from the SearchSource file"""
        # Not yet implemented

        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
            )
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Semantic Scholar"""
        # Not yet implemented
        return record
