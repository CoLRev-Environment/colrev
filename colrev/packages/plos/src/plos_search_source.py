#! /usr/bin/env python
"""SearchSource: plos"""
import datetime
import logging
import typing
from multiprocessing import Lock
from pathlib import Path

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.ops.prep
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.packages.doi_org.src.doi_org as doi_connector
import colrev.process.operation
import colrev.record.record
import colrev.record.record_prep
import colrev.search_file
import colrev.utils
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.packages.plos.src import plos_api


# pylint: disable=unused-argument
class PlosSearchSource(base_classes.SearchSourcePackageBaseClass):
    """PLOS API"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.plos"
    source_identifier = Fields.DOI
    search_types = [SearchType.API]
    heuristic_status = SearchSourceHeuristicStatus.oni

    _api_url = "http://api.plos.org/"

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
        self.plos_lock = Lock()
        self.language_service = colrev.env.language_service.LanguageService()

        self.api = plos_api.PlosAPI(url=self.search_source.search_parameters["url"])

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Heuristic to identify to which SearchSource a search file belongs (for DB searches)"""

        result = {"confidence": 0.0}
        return result

    @classmethod
    def _select_search_type(cls, params_dict: dict) -> SearchType:
        if "query" in params_dict:
            search_type = SearchType.API
        elif Fields.URL in params_dict:
            search_type = SearchType.API
        else:
            search_type = colrev.utils.select_search_type(
                search_types=cls.search_types, params=params_dict
            )

        return search_type

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add the SearchSource as an endpoint based on a query (passed to colrev search -a)
        params:
        - search_file="..." to add a DB search
        """
        params_dict: dict = {}
        search_type = cls._select_search_type(params_dict)
        if search_type == SearchType.API:
            if len(params) == 0:
                search_source = create_api_source(platform=cls.endpoint, path=path)

                search_source.search_parameters = {
                    "url": cls._api_url
                    + "search?"
                    + "q="
                    + search_source.search_string.replace(" ", "+")
                    + "&fl=id,abstract,author_display,title_display,"
                    + "journal,publication_date,volume,issue"
                }
                search_source.search_string = ""

                search_source.version = cls.CURRENT_SYNTAX_VERSION

                return search_source

            if Fields.URL in params_dict:
                query = {"url": params_dict[Fields.URL]}
            else:
                query = params_dict

            filename = colrev.utils.get_unique_filename(
                base_path=path,
                file_path_string="plos",
            )

            search_source = colrev.search_file.ExtendedSearchFile(
                version=cls.CURRENT_SYNTAX_VERSION,
                platform="colrev.plos",
                search_results_path=filename,
                search_type=SearchType.API,
                search_string="",
                search_parameters={"url": query["url"]},
                comment="",
            )

            return search_source

        raise NotImplementedError

    def _prep_plos_record(
        self,
        *,
        record: colrev.record.record.Record,
        prep_main_record: bool = True,
        plos_source: str = "",
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
            assert "" != plos_source
            record.set_status(RecordState.md_prepared)

    def _restore_url(
        self,
        *,
        record: colrev.record.record.Record,
        feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:
        "Restore the url from the feed if it exist"

        prev_record = feed.get_prev_feed_record(record)
        prev_url = prev_record.data.get(Fields.URL, None)

        if prev_url is None:
            return
        record.data[Fields.URL] = prev_url

    def _run_api_search(
        self,
        *,
        plos_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        self.api.rerun = rerun

        self.api.last_updated = plos_feed.get_last_updated()

        num_records = self.api.get_len_total()
        self.logger.info("Total: %s records", f"{num_records:,}")

        # It retrieves only new records added since the last sync, avoiding a full download.
        if not rerun:
            self.logger.info(
                "Retrieve papers indexed since %s",
                self.api.last_updated.split("T", maxsplit=1)[0],
            )
            num_records = self.api.get_len()

        self.logger.info("Retrieve %s records", f"{num_records:,}")

        estimated_time = num_records * 0.5
        estimated_time_formatted = str(datetime.timedelta(seconds=int(estimated_time)))
        self.logger.info("Estimated time: %s", estimated_time_formatted)

        try:
            for record in self.api.get_records():
                try:
                    if self._scope_excluded(record.data):
                        continue

                    self._prep_plos_record(record=record, prep_main_record=False)

                    self._restore_url(record=record, feed=plos_feed)
                    plos_feed.add_update_record(retrieved_record=record)

                except colrev_exceptions.NotFeedIdentifiableException:
                    pass
        except RuntimeError as e:
            print(e)

        plos_feed.save()

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

    def _validate_source(self) -> None:
        source = self.search_source

        if source.search_type not in self.search_types:
            raise colrev_exceptions.InvalidQueryException(
                f"Plos search_type should be in {self.search_types}"
            )

        if source.search_type == SearchType.API:
            self._validate_api_params()

        self.logger.debug(f"SearchSource {source.search_results_path} validated")

    # pylint: disable=pointless-statement
    def _validate_api_params(self) -> None:
        self.search_source

    def search(self, rerun: bool) -> None:
        """Run a search of the SearchSource"""
        self._validate_source()
        # Create the Object SearchAPIFeed which mange the search on the API

        plos_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        if self.search_source.search_type == SearchType.API:
            self._run_api_search(
                plos_feed=plos_feed,
                rerun=rerun,
            )
        else:
            raise NotImplementedError

    def load(self) -> dict:
        """Load records from the SearchSource (and convert to .bib)"""

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
        """Run the custom source-prep operation"""

        return record

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 30,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from Plos based on similarity with the record provided"""

        return record
