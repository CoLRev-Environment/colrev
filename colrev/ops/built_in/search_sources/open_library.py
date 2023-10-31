#! /usr/bin/env python
"""Connector to OpenLibrary (API)"""
from __future__ import annotations

import json
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils_bib
import colrev.record
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.prep

# Note: not (yet) implemented as a full search_source
# (including SearchSourcePackageEndpointInterface, packages_endpoints.json)


# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class OpenLibrarySearchSource(JsonSchemaMixin):
    """OpenLibrary API"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.open_library"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "isbn"
    search_types = [colrev.settings.SearchType.MD]

    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.na
    short_name = "OpenLibrary"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/open_library.md"
    )
    __open_library_md_filename = Path("data/search/md_open_library.bib")

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # OpenLibrary as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )

        else:
            # OpenLibrary as an md-prep source
            open_library_md_source_l = [
                s
                for s in self.review_manager.settings.sources
                if s.filename == self.__open_library_md_filename
            ]
            if open_library_md_source_l:
                self.search_source = open_library_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint="colrev.open_library",
                    filename=self.__open_library_md_filename,
                    search_type=colrev.settings.SearchType.MD,
                    search_parameters={},
                    comment="",
                )

            self.open_library_lock = Lock()

        self.origin_prefix = self.search_source.get_origin_prefix()

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
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
            requests_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
            }
            ret = requests.get(
                url,
                headers=requests_headers,
                timeout=30,
            )
            if ret.status_code != 200:
                if not source_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("OPENLIBRARY")
        except requests.exceptions.RequestException as exc:
            if not source_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "OPENLIBRARY"
                ) from exc

    # pylint: disable=colrev-missed-constant-usage
    @classmethod
    def __open_library_json_to_record(
        cls, *, item: dict, url: str
    ) -> colrev.record.PrepRecord:
        retrieved_record: dict = {}

        if "author_name" in item:
            authors_string = " and ".join(
                [
                    colrev.record.PrepRecord.format_author_field(input_string=author)
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

        record = colrev.record.PrepRecord(data=retrieved_record)
        record.add_provenance_all(source=url)
        return record

    def __get_record_from_open_library(
        self, *, prep_operation: colrev.ops.prep.Prep, record: colrev.record.Record
    ) -> colrev.record.Record:
        session = prep_operation.review_manager.get_cached_session()

        url = "NA"
        if Fields.ISBN in record.data:
            isbn = record.data[Fields.ISBN].replace("-", "").replace(" ", "")
            url = f"https://openlibrary.org/isbn/{isbn}.json"
            ret = session.request(
                "GET",
                url,
                headers=prep_operation.requests_headers,
                timeout=prep_operation.timeout,
            )
            ret.raise_for_status()
            # prep_operation.review_manager.logger.debug(url)
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
            ret = session.request(
                "GET",
                url,
                headers=prep_operation.requests_headers,
                timeout=prep_operation.timeout,
            )
            ret.raise_for_status()
            # prep_operation.review_manager.logger.debug(url)

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

        retrieved_record = self.__open_library_json_to_record(item=item, url=url)

        return retrieved_record

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for OpenLibrary"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        raise NotImplementedError

    def run_search(self, rerun: bool) -> None:
        """Run a search of OpenLibrary"""

        # if self.search_source.search_type == colrev.settings.SearchType.DB:
        #     if self.review_manager.in_ci_environment():
        #         raise colrev_exceptions.SearchNotAutomated(
        #             "DB search for OpenLibrary not automated."
        #         )

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Retrieve masterdata from OpenLibrary based on similarity with the record provided"""

        if any(self.origin_prefix in o for o in record.data[Fields.ORIGIN]):
            # Already linked to an open-library record
            return record

        try:
            retrieved_record = self.__get_record_from_open_library(
                prep_operation=prep_operation, record=record
            )

            self.open_library_lock.acquire(timeout=60)
            open_library_feed = self.search_source.get_feed(
                review_manager=prep_operation.review_manager,
                source_identifier=self.source_identifier,
                update_only=False,
            )

            open_library_feed.set_id(record_dict=retrieved_record.data)

            open_library_feed.add_record(record=retrieved_record)

            record.merge(
                merging_record=retrieved_record,
                default_source=retrieved_record.data[Fields.ORIGIN][0],
            )
            open_library_feed.save_feed_file()
            self.open_library_lock.release()

        except (
            colrev_exceptions.RecordNotFoundInPrepSourceException,
            requests.exceptions.RequestException,
        ):
            pass
        except (
            colrev_exceptions.InvalidMerge,
            colrev_exceptions.NotFeedIdentifiableException,
        ):
            self.open_library_lock.release()

        return record

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for OpenLibrary"""

        return record
