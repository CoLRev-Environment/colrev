#! /usr/bin/env python
"""Connector to OpenLibrary (API)"""
from __future__ import annotations

import json
import logging
import typing
from multiprocessing import Lock
from pathlib import Path

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
from colrev.packages.open_library.src import open_library_api

# Note: not (yet) implemented as a full search_source
# (including SearchSourcePackageBaseClass, packages_endpoints.json)


# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


class OpenLibrarySearchSource(base_classes.SearchSourcePackageBaseClass):
    """OpenLibrary API"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.open_library"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "isbn"
    search_types = [SearchType.MD]

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.na
    _availability_exception_message = "OPENLIBRARY"

    requests_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
    }

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

        self.open_library_lock = Lock()
        self.origin_prefix = self.search_source.get_origin_prefix()
        self.api = open_library_api.OpenLibraryAPI(
            session=colrev.utils.get_cached_session(),
            headers=self.requests_headers,
        )

    def check_availability(self) -> None:
        """Check the status (availability) of the OpenLibrary API"""

        test_rec = {
            Fields.ENTRYTYPE: "book",
            Fields.ISBN: "9781446201435",
            # 'author': 'Ridley, Diana',
            Fields.TITLE: "The Literature Review A Stepbystep Guide For Students",
            Fields.ID: "Ridley2012",
            Fields.YEAR: "2012",
        }
        try:
            url = f"https://openlibrary.org/isbn/{test_rec['isbn']}.json"
            self.api.get(url, timeout=30)
        except open_library_api.OpenLibraryAPIError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc
        except json.decoder.JSONDecodeError as exc:  # pragma: no cover
            raise colrev_exceptions.ServiceNotAvailableException(
                self._availability_exception_message
            ) from exc

    # pylint: disable=colrev-missed-constant-usage
    @classmethod
    def _open_library_json_to_record(
        cls, *, item: dict, url: str
    ) -> colrev.record.record_prep.PrepRecord:
        retrieved_record: dict = {}

        if "author_name" in item:
            authors_string = " and ".join(
                [
                    colrev.record.record_prep.PrepRecord.format_author_field(author)
                    for author in item["author_name"]
                ]
            )
            retrieved_record[Fields.AUTHOR] = authors_string
        if "publisher" in item:
            retrieved_record[Fields.PUBLISHER] = str(item["publisher"][0])
        if "title" in item:
            retrieved_record[Fields.TITLE] = str(item["title"])
        if "publish_year" in item:
            retrieved_record[Fields.YEAR] = str(item["publish_year"][0])
        if "edition_count" in item:
            retrieved_record[Fields.EDITOR] = str(item["edition_count"])
        if "seed" in item:
            if "/books/" in item["seed"][0]:
                retrieved_record[Fields.ENTRYTYPE] = "book"
        if "publish_place" in item:
            retrieved_record[Fields.ADDRESS] = str(item["publish_place"][0])
        if Fields.ISBN in item:
            retrieved_record[Fields.ISBN] = str(item["isbn"][0])

        record = colrev.record.record_prep.PrepRecord(retrieved_record)
        record.add_provenance_all(source=url)
        return record

    def _get_record_from_open_library(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
    ) -> colrev.record.record.Record:
        url = "NA"
        if Fields.ISBN in record.data:
            isbn = record.data[Fields.ISBN].replace("-", "").replace(" ", "")
            url = f"https://openlibrary.org/isbn/{isbn}.json"
            ret = self.api.get(url, timeout=prep_operation.timeout)
            # self.logger.debug(url)
            if '"error": "notfound"' in ret.text:
                record.remove_field(key=Fields.ISBN)

            item = json.loads(ret.text)

        else:
            base_url = "https://openlibrary.org/search.json?"
            url = ""
            if record.data.get(Fields.AUTHOR, "NA").split(",")[0]:
                url = (
                    base_url
                    + "&author="
                    + record.data.get(Fields.AUTHOR, "NA").split(",")[0]
                )
            if (
                record.data[Fields.ENTRYTYPE] == "inbook"
                and Fields.EDITOR in record.data
            ):
                if record.data.get(Fields.EDITOR, "NA").split(",")[0]:
                    url = (
                        base_url
                        + "&author="
                        + record.data.get(Fields.EDITOR, "NA").split(",")[0]
                    )
            if base_url not in url:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="OpenLibrary: base_url not in url"
                )

            title = record.data.get(
                Fields.TITLE, record.data.get(Fields.BOOKTITLE, "NA")
            )
            if len(title) < 10:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="OpenLibrary: len(title) < 10"
                )
            if ":" in title:
                title = title[: title.find(":")]  # To catch sub-titles
            url = url + "&title=" + title.replace(" ", "+")
            ret = self.api.get(url, timeout=prep_operation.timeout)
            # self.logger.debug(url)

            # if we have an exact match, we don't need to check the similarity
            if '"numFoundExact": true,' not in ret.text:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="OpenLibrary: numFoundExact true missing"
                )

            data = json.loads(ret.text)
            items = data["docs"]
            if not items:
                raise colrev_exceptions.RecordNotFoundInPrepSourceException(
                    msg="OpenLibrary: no items"
                )
            item = items[0]

        retrieved_record = self._open_library_json_to_record(item=item, url=url)

        return retrieved_record

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for OpenLibrary"""

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
        raise NotImplementedError

    def search(self, rerun: bool) -> None:
        """Run a search of OpenLibrary"""

        # if self.search_source.search_type == SearchType.DB:
        #     if utils.in_ci_environment():
        #         raise colrev_exceptions.SearchNotAutomated(
        #             "DB search for OpenLibrary not automated."
        #         )

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from OpenLibrary based on similarity with the record provided"""

        if any(self.origin_prefix in o for o in record.data[Fields.ORIGIN]):
            # Already linked to an open-library record
            return record

        try:
            retrieved_record = self._get_record_from_open_library(
                prep_operation=prep_operation, record=record
            )

            self.open_library_lock.acquire(timeout=60)
            open_library_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                source_identifier=self.source_identifier,
                search_source=self.search_source,
                update_only=False,
                prep_mode=True,
                records=prep_operation.review_manager.dataset.load_records_dict(),
                logger=self.logger,
                verbose_mode=self.verbose_mode,
            )

            open_library_feed.add_update_record(retrieved_record)

            record.merge(
                retrieved_record,
                default_source=retrieved_record.data[Fields.ORIGIN][0],
            )
            prep_operation.review_manager.dataset.save_records_dict(
                open_library_feed.get_records(),
            )
            open_library_feed.save()
            self.open_library_lock.release()

        except (colrev_exceptions.RecordNotFoundInPrepSourceException,):
            pass
        except (colrev_exceptions.NotFeedIdentifiableException,):
            self.open_library_lock.release()

        return record

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

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
    ) -> colrev.record.record.Record:
        """Source-specific preparation for OpenLibrary"""

        return record
