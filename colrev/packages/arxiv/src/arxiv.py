#! /usr/bin/env python
"""SearchSource: arXiv"""
from __future__ import annotations

import logging
import typing
from multiprocessing import Lock
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import feedparser
import requests
from pydantic import Field

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
from colrev.packages.arxiv.src import record_transformer

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class ArXivSource(base_classes.SearchSourcePackageBaseClass):
    """arXiv"""

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
        source_operation: colrev.process.operation.Operation,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode
        self.review_manager = source_operation.review_manager
        self.search_source = search_file

        self.arxiv_lock = Lock()

        self.operation = source_operation
        self.quality_model = self.review_manager.get_qm()
        _, self.email = self.review_manager.get_committer()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ArXiv"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
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
            search_source = operation.create_api_source(platform=cls.endpoint)

        # pylint: disable=colrev-missed-constant-usage
        else:
            host = urlparse(params_dict["url"]).hostname

            assert host and host.endswith("arxiv.org")

            query = params_dict["url"].replace("https://arxiv.org/search/?query=", "")
            query = query[: query.find("&searchtype")]

            filename = colrev.utils.get_unique_filename(
                review_manager=operation.review_manager,
                file_path_string="arxiv",
            )

            search_source = colrev.search_file.ExtendedSearchFile(
                platform="colrev.arxiv",
                search_results_path=filename,
                search_type=SearchType.API,
                search_string="",
                search_parameters={"query": query},
                comment="",
            )

        operation.add_source_and_search(search_source)
        return search_source

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.search_file.ExtendedSearchFile,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        self.logger.debug(f"Validate SearchSource {source.filename}")

        if source.filename.name != self._arxiv_md_filename.name:
            if "query" not in source.search_string:
                raise colrev_exceptions.InvalidQueryException(
                    f"Source missing query search_parameter ({source.filename})"
                )

            # if "query_file" in source.search_string:
            # ...

        self.logger.debug(f"SearchSource {source.filename} validated")

    def check_availability(self) -> None:
        """Check status (availability) of the ArXiv API"""

        try:
            ret = requests.get(
                "https://export.arxiv.org/api/query?search_query=all:electron&start=0&max_results=1",
                timeout=30,
            )
            ret.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    # def _arxiv_query_id(
    #     self,
    #     *,
    #     arxiv_id: str,
    #     timeout: int = 60,
    # ) -> dict:
    #     """Retrieve records from ArXiv based on a query"""

    #     # Query using ID List prefix ?? - wo hast du das gefunden?
    #     try:
    #         prefix = "id_list"
    #         url = (
    #             "https://export.arxiv.org/api/query?search_query="
    #             + f"list={prefix}:&id={arxiv_id}"
    #         )

    #         headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
    #         session = colrev.utils.get_cached_session()

    #         # self.logger.debug(url)
    #         ret = session.request("GET", url, headers=headers, timeout=timeout)
    #         ret.raise_for_status()
    #         if ret.status_code != 200:
    #             # self.logger.debug(
    #             #     f"crossref_query failed with status {ret.status_code}"
    #             # )
    #             return {"arxiv_id": arxiv_id}

    #         input(str.encode(ret.text))
    #         root = fromstring(str.encode(ret.text))
    #         retrieved_record = self._arxiv_xml_to_record(root=root)
    #         if not retrieved_record:
    #             return {"arxiv_id": arxiv_id}
    #     except requests.exceptions.RequestException:
    #         return {"arxiv_id": arxiv_id}
    #     # pylint: disable=duplicate-code
    #     except OperationalError as exc:
    #         raise colrev_exceptions.ServiceNotAvailableException(
    #             "sqlite, required for requests CachedSession "
    #             "(possibly caused by concurrent operations)"
    #         ) from exc

    #     return retrieved_record

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

    def _get_arxiv_ids(self, query: str, retstart: int) -> typing.List[dict]:
        url = (
            "https://export.arxiv.org/api/query?search_query="
            + f"all:{query}&start={retstart}&max_results=20"
        )
        feed = feedparser.parse(url)
        return feed["entries"]

    def _get_arxiv_query_return(self) -> typing.Iterator[dict]:
        params = self.search_source.search_string
        retstart = 0
        while True:
            entries = self._get_arxiv_ids(query=params["query"], retstart=retstart)
            if not entries:
                break
            for entry in entries:
                yield record_transformer.parse_record(entry)

            retstart += 20

    def _run_parameter_search(
        self,
        *,
        arxiv_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        if rerun:
            self.logger.info("Performing a search of the full history (may take time)")

        try:
            for record_dict in self._get_arxiv_query_return():
                try:
                    # Note : discard "empty" records
                    if "" == record_dict.get(
                        Fields.AUTHOR, ""
                    ) and "" == record_dict.get(Fields.TITLE, ""):
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

        except requests.exceptions.JSONDecodeError as exc:
            # watch github issue:
            # https://github.com/fabiobatalha/crossrefapi/issues/46
            if "504 Gateway Time-out" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Crossref (check https://status.crossref.org/)"
                )
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Crossref (check https://status.crossref.org/) ({exc})"
            )

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

    @classmethod
    def load(cls, *, filename: Path, logger: logging.Logger) -> dict:
        """Load the records from the SearchSource file"""

        # for API-based searches
        if filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=filename,
                logger=logger,
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
        record: colrev.record.record.Record,
        source: colrev.search_file.ExtendedSearchFile,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for ArXiv"""

        if Fields.AUTHOR in record.data:
            record.data[Fields.AUTHOR] = (
                colrev.record.record_prep.PrepRecord.format_author_field(
                    record.data[Fields.AUTHOR]
                )
            )

        return record
