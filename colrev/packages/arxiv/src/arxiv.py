#! /usr/bin/env python
"""SearchSource: arXiv"""
from __future__ import annotations

import logging
import typing
from multiprocessing import Lock
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.record.record_prep
import colrev.search_file
import colrev.utils
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.packages.arxiv.src import arxiv_api


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class ArXivSource(base_classes.SearchSourcePackageBaseClass):
    """arXiv"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.arxiv"
    source_identifier = "arxivid"
    search_types = [SearchType.API]
    api_search_supported = True
    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.supported
    db_url = "https://arxiv.org/"
    _arxiv_md_filename = Path("data/search/md_arxiv.bib")
    _availability_exception_message = "ArXiv"

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

        self.arxiv_lock = Lock()

        _, self.email = (
            colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git()
        )
        self.api = arxiv_api.ArxivAPI(search_file=search_file)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ArXiv"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        # Note : always API search
        if len(params_dict) == 0:
            search_source = create_api_source(platform=cls.endpoint, path=path)
            search_source.search_parameters = {"query": search_source.search_string}
            search_source.search_string = ""

        # pylint: disable=colrev-missed-constant-usage
        else:
            host = urlparse(params_dict["url"]).hostname

            assert host and host.endswith("arxiv.org")

            query = params_dict["url"].replace("https://arxiv.org/search/?query=", "")
            query = query[: query.find("&searchtype")]

            filename = colrev.utils.get_unique_filename(
                base_path=path,
                file_path_string="arxiv",
            )

            search_source = colrev.search_file.ExtendedSearchFile(
                version=cls.CURRENT_SYNTAX_VERSION,
                platform="colrev.arxiv",
                search_results_path=filename,
                search_type=SearchType.API,
                search_string="",
                search_parameters={"query": query},
                comment="",
            )
        return search_source

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.search_file.ExtendedSearchFile,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        self.logger.debug(f"Validate SearchSource {source.search_results_path}")

        if source.search_results_path.name != self._arxiv_md_filename.name:
            if "query" not in source.search_string:
                raise colrev_exceptions.InvalidQueryException(
                    f"Source missing query search_parameter ({source.search_results_path})"
                )

            # if "query_file" in source.search_string:
            # ...

        self.logger.debug(f"SearchSource {source.search_results_path} validated")

    def check_availability(self) -> None:
        """Check status (availability) of the ArXiv API"""

        try:
            self.api.check_availability(timeout=30)
        except arxiv_api.ArxivAPIError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata fromArXiv based on similarity with the record provided"""
        # https://info.arxiv.org/help/api/user-manual.html#_query_interface
        # id_list
        return record

    def _run_parameter_search(
        self,
        *,
        arxiv_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        if rerun:
            self.logger.info("Performing a search of the full history (may take time)")

        for record_dict in self.api.get_arxiv_query_return():
            try:
                # Note : discard "empty" records
                if "" == record_dict.get(Fields.AUTHOR, "") and "" == record_dict.get(
                    Fields.TITLE, ""
                ):
                    self.logger.warning(f"Skipped record: {record_dict}")
                    continue

                prep_record = colrev.record.record_prep.PrepRecord(record_dict)

                added = arxiv_feed.add_update_record(prep_record)

                # Note : only retrieve/update the latest deposits (unless in rerun mode)
                if not added and not rerun:
                    # problem: some publishers don't necessarily
                    # deposit papers chronologically
                    break
            except colrev_exceptions.NotFeedIdentifiableException:
                continue

        arxiv_feed.save()

    # def _run_md_search_update(
    #     self,
    #     *,
    #     arxiv_feed: colrev.ops.search.SearchAPIFeed,
    # ) -> None:
    #     records = self.review_manager.dataset.load_records_dict()

    #     for feed_record_dict in arxiv_feed.feed_records.values():
    #         feed_record = colrev.record.record.Record(feed_record_dict)

    #         try:
    #             retrieved_record = self._arxiv_query_id(
    #                 arxiv_id=feed_record_dict["arxivid"]
    #             )

    #             if retrieved_record["arxivid"] != feed_record.data["arxivid"]:
    #                 continue

    # prev_record_dict_version = (
    #     dblp_feed.get_prev_feed_record(
    #         retrieved_record=feed_record
    #     )
    # )
    #         retrieved_record = colrev.record.record.Record(retrieved_record)
    #         arxiv_feed.add_update_record(retrieved_record)

    #         changed = self.operation.update_existing_record(
    #             records=records,
    #             record_dict=retrieved_record,
    #             prev_record_dict_version=prev_record_dict_version,
    #             source=self.search_source,
    #         )
    #         if changed:
    #             arxiv_feed.nr_changed += 1
    #         except (
    #             colrev_exceptions.RecordNotFoundInPrepSourceException,
    #             colrev_exceptions.NotFeedIdentifiableException,
    #         ):
    #             continue

    #     arxiv_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of ArXiv"""

        arxiv_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        # if self.search_source.search_type == SearchType.MD:
        #     self._run_md_search_update(
        #         arxiv_feed=arxiv_feed,
        #     )

        if self.search_source.search_type == SearchType.API:
            self._run_parameter_search(
                arxiv_feed=arxiv_feed,
                rerun=rerun,
            )

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        # for API-based searches
        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
            )
            for record in records.values():
                record[Fields.INSTITUTION] = "ArXiv"
            return records

        raise NotImplementedError

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.search_file.ExtendedSearchFile,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for ArXiv"""
        return records

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for ArXiv"""

        if Fields.AUTHOR in record.data:
            record.data[Fields.AUTHOR] = (
                colrev.record.record_prep.PrepRecord.format_author_field(
                    record.data[Fields.AUTHOR]
                )
            )

        return record
