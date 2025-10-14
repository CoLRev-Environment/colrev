#! /usr/bin/env python
"""SearchSource: Crossref"""
from __future__ import annotations

import datetime
import logging
import typing
from multiprocessing import Lock
from pathlib import Path

import inquirer
from pydantic import Field

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.packages.doi_org.src.doi_org as doi_connector
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
import colrev.search_file
import colrev.utils
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.packages.crossref.src import crossref_api
from colrev.packages.crossref.src.crossref_api import query_doi

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class CrossrefSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Crossref API"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.crossref"
    source_identifier = Fields.DOI

    search_types = [
        SearchType.API,
        SearchType.MD,
        SearchType.TOC,
    ]

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.oni

    _api_url = "https://api.crossref.org/"

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode

        self.search_source = search_file
        self._validate_source()
        self.crossref_lock = Lock()
        self.language_service = colrev.env.language_service.LanguageService()

        url = ""
        if self.search_source.search_type == SearchType.MD:
            url = self._api_url
        else:
            url = self.search_source.search_parameters["url"]

        self.api = crossref_api.CrossrefAPI(url=url)

    def _validate_source(self) -> None:
        # validate version and migrate if needed
        # TBD: automatically migrate (option to skip?)
        source = self.search_source
        self.logger.debug(f"Validate SearchSource {source.search_results_path}")
        if source.search_type not in self.search_types:
            raise colrev_exceptions.InvalidQueryException(
                f"Crossref search_type should be in {self.search_types}"
            )

        # if source.version == "0.1.0":
        # migration here...

        if source.version != self.CURRENT_SYNTAX_VERSION:
            raise colrev_exceptions.InvalidQueryException(
                f"Crossref version should be {self.CURRENT_SYNTAX_VERSION}, found {source.version}"
            )

        # logic to validate the latest version
        if source.search_string != "":
            raise colrev_exceptions.InvalidQueryException(
                "Crossref search_string should be empty - use search_parameters"
            )
        if source.search_type == SearchType.API:
            self._validate_api_params()

        self.logger.debug("SearchSource %s validated", source.search_results_path)

    def _validate_api_params(self) -> None:
        pass
        # self.search_source

        # if not all(x in ["url", "version"] for x in source.search_string):
        #     raise colrev_exceptions.InvalidQueryException(
        #         "Crossref search_string supports query or scope/issn field"
        #     )
        # Validate Query here

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Crossref"""

        result = {"confidence": 0.0}
        return result

    @classmethod
    def _parse_params(cls, params: str) -> dict:
        # pylint: disable=colrev-missed-constant-usage
        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        if "issn" in params_dict:
            params_dict["scope"] = {Fields.ISSN: [params_dict["issn"]]}  # type: ignore
            del params_dict["issn"]
        if "scope" in params_dict:
            issn = params_dict["scope"][Fields.ISSN][0]  # type: ignore
            params_dict["url"] = f"https://api.crossref.org/journals/{issn}/works"
        return params_dict

    @classmethod
    def _select_search_type(cls, params_dict: dict) -> SearchType:
        if list(params_dict) == ["scope"]:
            search_type = SearchType.TOC
        elif "query" in params_dict:
            search_type = SearchType.API
        elif Fields.URL in params_dict:
            search_type = SearchType.API
        else:
            search_type = colrev.utils.select_search_type(
                search_types=cls.search_types, params=params_dict
            )

        return search_type

    @classmethod
    def _add_toc_interactively(
        cls, *, path: Path
    ) -> colrev.search_file.ExtendedSearchFile:

        j_name = input("Enter journal name to lookup the ISSN:")

        url = "https://api.crossref.org/journals?query=" + j_name.replace(" ", "+")
        endpoint = crossref_api.Endpoint(url)

        questions = [
            inquirer.List(
                Fields.JOURNAL,
                message="Select journal:",
                choices=[{x[Fields.TITLE]: x["ISSN"]} for x in endpoint],
            ),
        ]
        answers = inquirer.prompt(questions)
        issn = list(answers[Fields.JOURNAL].values())[0][0]

        filename = colrev.utils.get_unique_filename(
            base_path=path,
            file_path_string=f"crossref_issn_{issn}",
        )
        add_source = colrev.search_file.ExtendedSearchFile(
            platform="colrev.crossref",
            search_results_path=filename,
            search_type=SearchType.TOC,
            search_string="",
            search_params={
                "url": f"https://api.crossref.org/journals/{issn.replace('-', '')}/works"
            },
            version=cls.CURRENT_SYNTAX_VERSION,
            comment="",
        )
        return add_source

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint"""
        params_dict = cls._parse_params(params)
        search_type = cls._select_search_type(params_dict)

        if search_type == SearchType.API:
            if len(params_dict) == 0:
                search_source = create_api_source(platform=cls.endpoint, path=path)
                # pylint: disable=colrev-missed-constant-usage
                search_source.search_parameters = {}
                search_source.search_parameters["url"] = (
                    cls._api_url
                    + "works?"
                    + "query.bibliographic="
                    + search_source.search_string.replace(" ", "+")
                )
                search_source.search_string = ""
                search_source.version = cls.CURRENT_SYNTAX_VERSION
            else:
                if Fields.URL in params_dict:
                    query = {"url": params_dict[Fields.URL]}
                else:
                    query = params_dict

                filename = colrev.utils.get_unique_filename(
                    base_path=path,
                    file_path_string="crossref",
                )
                search_source = colrev.search_file.ExtendedSearchFile(
                    platform="colrev.crossref",
                    search_results_path=filename,
                    search_type=SearchType.API,
                    search_string="",
                    search_parameters={
                        "query": query["url"],
                    },
                    comment="",
                    version=cls.CURRENT_SYNTAX_VERSION,
                )

        elif search_type == SearchType.TOC:
            if len(params_dict) == 0:
                search_source = cls._add_toc_interactively(path=path)
                search_source.search_parameters = {
                    "url": search_source.search_string,
                }
                search_source.version = cls.CURRENT_SYNTAX_VERSION
                search_source.search_string = ""
            else:
                filename = colrev.utils.get_unique_filename(
                    base_path=path,
                    file_path_string="crossref",
                )
                search_source = colrev.search_file.ExtendedSearchFile(
                    platform="colrev.crossref",
                    search_results_path=filename,
                    search_type=SearchType.TOC,
                    search_string="",
                    search_parameters={
                        "url": params_dict["url"],
                    },
                    comment="",
                    version=cls.CURRENT_SYNTAX_VERSION,
                )

        else:
            raise NotImplementedError
        return search_source

    def check_availability(self) -> None:
        """Check status (availability) of the Crossref API"""
        self.api.check_availability()

    def _prep_crossref_record(
        self,
        *,
        record: colrev.record.record.Record,
        prep_main_record: bool = True,
        crossref_source: str = "",
    ) -> None:
        if Fields.LANGUAGE in record.data:
            try:
                self.language_service.unify_to_iso_639_3_language_codes(record=record)
            except colrev_exceptions.InvalidLanguageCodeException:
                del record.data[Fields.LANGUAGE]

        doi_connector.DOIConnector.get_link_from_doi(
            record=record,
        )

        if not prep_main_record:
            # Skip steps for feed records
            return

        if FieldValues.RETRACTED in record.data.get(
            "warning", ""
        ) or FieldValues.RETRACTED in record.data.get(Fields.PRESCREEN_EXCLUSION, ""):
            record.prescreen_exclude(reason=FieldValues.RETRACTED)
            record.remove_field(key="warning")
        else:
            record.set_status(RecordState.md_prepared)

    def _restore_url(
        self,
        *,
        record: colrev.record.record.Record,
        feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:
        """Restore the url from the feed if it exists
        (url-resolution is not always available)"""
        prev_record = feed.get_prev_feed_record(record)
        prev_url = prev_record.data.get(Fields.URL, None)
        if prev_url is None:
            return
        record.data[Fields.URL] = prev_url

    def _run_md_search(
        self,
        crossref_feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:

        for feed_record_dict in crossref_feed.feed_records.values():
            try:
                retrieved_record = query_doi(doi=feed_record_dict[Fields.DOI])

                if retrieved_record.data[Fields.DOI] != feed_record_dict[Fields.DOI]:
                    continue

                self._prep_crossref_record(
                    record=retrieved_record, prep_main_record=False
                )

                self._restore_url(record=retrieved_record, feed=crossref_feed)
                crossref_feed.add_update_record(retrieved_record)

            except (
                colrev_exceptions.RecordNotFoundInPrepSourceException,
                colrev_exceptions.NotFeedIdentifiableException,
            ):
                continue

        crossref_feed.save()

    def _scope_excluded(self, retrieved_record_dict: dict) -> bool:
        if (
            "scope" not in self.search_source.search_parameters
            or "years" not in self.search_source.search_parameters["scope"]
        ):
            return False

        year_from, year_to = self.search_source.search_parameters["scope"][
            "years"
        ].split("-")
        if not retrieved_record_dict.get(Fields.YEAR, -1000).isdigit():
            return True

        if (
            int(year_from)
            < int(retrieved_record_dict.get(Fields.YEAR, -1000))
            < int(year_to)
        ):
            return False
        return True

    def _potentially_overlapping_issn_search(self) -> bool:
        params = self.search_source.search_parameters
        if "scope" not in params:
            return False
        if Fields.ISSN not in params["scope"]:
            return False
        return len(params["scope"][Fields.ISSN]) > 1

    def _run_api_search(
        self,
        *,
        crossref_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:

        self.logger.info("Retrieving from %s", self.api.url)
        self.api.rerun = rerun
        self.api.last_updated = crossref_feed.get_last_updated()

        nrecs = self.api.get_len_total()

        self.logger.info(f"Total: {nrecs:,} records")
        if not rerun:
            self.logger.info(
                "Retrieve papers indexed since %s",
                self.api.last_updated.split("T", maxsplit=1)[0],
            )
            nrecs = self.api.get_number_of_records()

        self.logger.info("Retrieve %s records", f"{nrecs:,}")
        estimated_time = nrecs * 0.5
        estimated_time_formatted = str(datetime.timedelta(seconds=int(estimated_time)))
        self.logger.info("Estimated time: %s", estimated_time_formatted)

        try:
            for retrieved_record in self.api.get_records():
                try:
                    if self._scope_excluded(retrieved_record.data):
                        continue

                    self._prep_crossref_record(
                        record=retrieved_record, prep_main_record=False
                    )

                    self._restore_url(record=retrieved_record, feed=crossref_feed)

                    crossref_feed.add_update_record(retrieved_record=retrieved_record)

                except colrev_exceptions.NotFeedIdentifiableException:
                    pass
        except RuntimeError as exc:
            print(exc)

        crossref_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of Crossref"""

        crossref_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        if self.search_source.search_type in [
            SearchType.API,
            SearchType.TOC,
        ]:
            self._run_api_search(
                crossref_feed=crossref_feed,
                rerun=rerun,
            )
        elif self.search_source.search_type == SearchType.MD:
            self._run_md_search(crossref_feed)
        else:
            raise NotImplementedError

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
                unique_id_field="ID",
            )
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Crossref"""

        return record

    def _get_masterdata_record(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool,
    ) -> colrev.record.record.Record:
        try:
            try:
                retrieved_record = query_doi(doi=record.data[Fields.DOI])
            except (colrev_exceptions.RecordNotFoundInPrepSourceException, KeyError):

                retrieved_records = self.api.crossref_query(
                    record_input=record,
                    jour_vol_iss_list=False,
                )
                retrieved_record = retrieved_records.pop()

                retries = 0
                while (
                    not retrieved_record
                    and retries < prep_operation.max_retries_on_error
                ):
                    retries += 1

                    retrieved_records = self.api.crossref_query(
                        record_input=record,
                        jour_vol_iss_list=False,
                    )
                    retrieved_record = retrieved_records.pop()

            if not colrev.record.record_similarity.matches(record, retrieved_record):
                return record

            try:
                self.crossref_lock.acquire(timeout=120)

                # Note : need to reload file because the object is not shared between processes
                crossref_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                    source_identifier=self.source_identifier,
                    search_source=self.search_source,
                    update_only=False,
                    prep_mode=True,
                    records=prep_operation.review_manager.dataset.load_records_dict(),
                    logger=self.logger,
                    verbose_mode=self.verbose_mode,
                )

                crossref_feed.add_update_record(retrieved_record)

                record.merge(
                    retrieved_record,
                    default_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                self._prep_crossref_record(
                    record=record,
                    crossref_source=retrieved_record.data[Fields.ORIGIN][0],
                )

                if save_feed:
                    prep_operation.review_manager.dataset.save_records_dict(
                        crossref_feed.get_records(),
                    )
                    crossref_feed.save()

            except colrev_exceptions.NotFeedIdentifiableException:
                pass
            finally:
                try:
                    self.crossref_lock.release()
                except ValueError:
                    pass

            return record

        except (
            colrev_exceptions.ServiceNotAvailableException,
            OSError,
            IndexError,
            colrev_exceptions.RecordNotFoundInPrepSourceException,
            colrev_exceptions.RecordNotParsableException,
        ) as exc:
            if self.verbose_mode:
                print(exc)

        return record

    def _check_doi_masterdata(
        self, record: colrev.record.record.Record
    ) -> colrev.record.record.Record:
        try:
            retrieved_record = query_doi(doi=record.data[Fields.DOI])
            if not colrev.record.record_similarity.matches(record, retrieved_record):
                self.logger.info(" remove DOI (not matching metadata)")
                record.remove_field(key=Fields.DOI)

        except (
            crossref_api.CrossrefAPIError,
            OSError,
            IndexError,
            colrev_exceptions.RecordNotFoundInPrepSourceException,
            colrev_exceptions.RecordNotParsableException,
        ):
            pass

        return record

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 30,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from Crossref based on similarity with the record provided"""

        # To test the metadata provided for a particular DOI use:
        # https://api.crossref.org/works/DOI
        if len(record.data.get(Fields.TITLE, "")) < 5 and Fields.DOI not in record.data:
            return record

        if Fields.DOI in record.data:
            record = self._check_doi_masterdata(record=record)

        record = self._get_masterdata_record(
            prep_operation=prep_operation,
            record=record,
            save_feed=save_feed,
        )

        return record
