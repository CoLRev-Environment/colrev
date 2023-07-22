#! /usr/bin/env python
"""SearchSource: OpenAlex"""
from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import pyalex
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from pyalex import Works

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils_bib
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.search
    import colrev.ops.prep

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class OpenAlexSearchSource(JsonSchemaMixin):
    """SearchSource for the OpenAlex API"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "openalex_id"
    # "https://api.crossref.org/works/{{doi}}"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/open_alex.md"
    )
    short_name = "OpenAlex"
    __open_alex_md_filename = Path("data/search/md_open_alex.bib")

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        # Note: not yet implemented
        # Note : once this is implemented, add "colrev.open_alex_prep" to the default settings
        # if settings:
        #     # OpenAlex as a search_source
        #     self.search_source = from_dict(
        #         data_class=self.settings_class, data=settings
        #     )
        # else:
        # OpenAlex as an md-prep source
        open_alex_md_source_l = [
            s
            for s in source_operation.review_manager.settings.sources
            if s.filename == self.__open_alex_md_filename
        ]
        if open_alex_md_source_l:
            self.search_source = open_alex_md_source_l[0]
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint="colrev.open_alex",
                filename=self.__open_alex_md_filename,
                search_type=colrev.settings.SearchType.OTHER,
                search_parameters={},
                comment="",
            )

        self.open_alex_lock = Lock()

        self.language_service = colrev.env.language_service.LanguageService()

        self.review_manager = source_operation.review_manager
        _, pyalex.config.email = self.review_manager.get_committer()

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of the OpenAlex API"""

    def __set_author_from_item(self, *, record_dict: dict, item: dict) -> None:
        ret_str = ""
        for author in item["authorships"]:
            if "author" not in author:
                continue
            if author["author"].get("display_name", None) is None:
                continue
            author_string = colrev.record.PrepRecord.format_author_field(
                input_string=author["author"]["display_name"]
            )
            if ret_str == "":
                ret_str = author_string
            else:
                ret_str += " and " + author_string
        if ret_str != "":
            record_dict["author"] = ret_str

    def __parse_item_to_record(self, *, item: dict) -> colrev.record.Record:
        record_dict = {}
        record_dict["openalex_id"] = item["id"].replace("https://openalex.org/", "")

        record_dict["title"] = item.get("title", "")
        if record_dict["title"] is None:
            del record_dict["title"]
        if item["type"] == "journal-article":
            record_dict["ENTRYTYPE"] = "article"
            if (
                item.get("primary_location", None) is not None
                and item["primary_location"].get("source", None) is not None
            ):
                record_dict["journal"] = item["primary_location"]["source"][
                    "display_name"
                ]
        else:
            record_dict["ENTRYTYPE"] = "misc"

        if "publication_year" in item and item["publication_year"] is not None:
            record_dict["year"] = str(item["publication_year"])
        if "language" in item and item["language"] is not None:
            record_dict["language"] = item["language"]

        if "is_retracted" in item and item["is_retracted"]:
            record_dict["retracted"] = item["is_retracted"]

        if "doi" in item and item["doi"] is not None:
            record_dict["doi"] = item["doi"].upper().replace("HTTPS://DOI.ORG/", "")

        record_dict["cited_by"] = item["cited_by_count"]

        if "volume" in item["biblio"] and item["biblio"]["volume"] is not None:
            record_dict["volume"] = item["biblio"]["volume"]
        if "issue" in item["biblio"] and item["biblio"]["issue"] is not None:
            record_dict["number"] = item["biblio"]["issue"]
        if "first_page" in item["biblio"] and item["biblio"]["first_page"] is not None:
            record_dict["pages"] = item["biblio"]["first_page"]
        if "last_page" in item["biblio"] and item["biblio"]["last_page"] is not None:
            record_dict["pages"] += "--" + item["biblio"]["last_page"]

        self.__set_author_from_item(record_dict=record_dict, item=item)
        record = colrev.record.Record(data=record_dict)

        self.__fix_errors(record=record)
        return record

    def __fix_errors(self, *, record: colrev.record.Record) -> None:
        if "PubMed" == record.data.get("journal", ""):
            record.remove_field(key="journal")
        try:
            self.language_service.unify_to_iso_639_3_language_codes(record=record)
        except colrev_exceptions.InvalidLanguageCodeException:
            record.remove_field(key="language")

    def __get_masterdata_record(
        self, *, record: colrev.record.Record
    ) -> colrev.record.Record:
        try:
            retrieved_record = self.__parse_item_to_record(
                item=Works()[record.data["openalex_id"]]
            )

            self.open_alex_lock.acquire(timeout=120)

            # Note : need to reload file because the object is not shared between processes
            open_alex_feed = self.search_source.get_feed(
                review_manager=self.review_manager,
                source_identifier=self.source_identifier,
                update_only=False,
            )

            open_alex_feed.set_id(record_dict=retrieved_record.data)
            open_alex_feed.add_record(record=retrieved_record)

            record.merge(
                merging_record=retrieved_record,
                default_source=retrieved_record.data["colrev_origin"][0],
            )
            open_alex_feed.save_feed_file()
        except (
            colrev_exceptions.InvalidMerge,
            colrev_exceptions.RecordNotParsableException,
        ):
            pass
        except Exception as exc:
            raise exc
        finally:
            self.open_alex_lock.release()

        return record

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 30,
    ) -> colrev.record.Record:
        """Retrieve masterdata from OpenAlex based on similarity with the record provided"""

        if "openalex_id" not in record.data:
            # Note: not yet implemented
            # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
            # if len(record.data.get("title", "")) < 35 and "doi" not in record.data:
            #     return record
            # record = self.__check_doi_masterdata(record=record)
            return record

        record = self.__get_masterdata_record(record=record)

        return record

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )
        # Note: not yet implemented

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of OpenAlex"""

        # https://docs.openalex.org/api-entities/works

        # crossref_feed = self.search_source.get_feed(
        #     review_manager=search_operation.review_manager,
        #     source_identifier=self.source_identifier,
        #     update_only=(not rerun),
        # )

        # try:
        #     if (
        #         self.search_source.is_md_source()
        #         or self.search_source.is_quasi_md_source()
        #     ):
        #         self.__run_md_search_update(
        #             search_operation=search_operation,
        #             crossref_feed=crossref_feed,
        #         )

        #     else:
        #         self.__run_parameter_search(
        #             search_operation=search_operation,
        #             crossref_feed=crossref_feed,
        #             rerun=rerun,
        #         )
        # except (
        #     requests.exceptions.Timeout,
        #     requests.exceptions.JSONDecodeError,
        # ) as exc:
        #     # watch github issue:
        #     # https://github.com/fabiobatalha/crossrefapi/issues/46
        #     if "504 Gateway Time-out" in str(exc):
        #         raise colrev_exceptions.ServiceNotAvailableException(
        #             self.__availability_exception_message
        #         )
        #     raise colrev_exceptions.ServiceNotAvailableException(
        #         self.__availability_exception_message
        #     )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for OpenAlex"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        raise colrev_exceptions.PackageParameterError(
            f"Cannot add OpenAlex endpoint with query {query}"
        )

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
        """Source-specific preparation for OpenAlex"""

        return record
