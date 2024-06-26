#! /usr/bin/env python
"""SearchSource: OpenAlex"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path

import pyalex
import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from pyalex import Works

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.record.record_prep
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class OpenAlexSearchSource(JsonSchemaMixin):
    """OpenAlex API"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.open_alex"
    source_identifier = "openalex_id"
    # "https://api.crossref.org/works/{{doi}}"
    search_types = [SearchType.API, SearchType.MD]

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.oni
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/search_sources/open_alex.md"
    )
    short_name = "OpenAlex"
    _open_alex_md_filename = Path("data/search/md_open_alex.bib")

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        # Note: not yet implemented
        # Note : once this is implemented, add "colrev.open_alex" to the default settings
        # if settings:
        #     # OpenAlex as a search_source
        #     self.search_source = from_dict(
        #         data_class=self.settings_class, data=settings
        #     )
        # else:
        # OpenAlex as an md-prep source
        open_alex_md_source_l = [
            s
            for s in self.review_manager.settings.sources
            if s.filename == self._open_alex_md_filename
        ]
        if open_alex_md_source_l:
            self.search_source = open_alex_md_source_l[0]
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint="colrev.open_alex",
                filename=self._open_alex_md_filename,
                search_type=SearchType.MD,
                search_parameters={},
                comment="",
            )

        self.open_alex_lock = Lock()

        self.language_service = colrev.env.language_service.LanguageService()

        _, pyalex.config.email = self.review_manager.get_committer()

    def check_availability(
        self, *, source_operation: colrev.process.operation.Operation
    ) -> None:
        """Check status (availability) of the OpenAlex API"""

    def _set_author_from_item(self, *, record_dict: dict, item: dict) -> None:
        author_list = []
        # pylint: disable=colrev-missed-constant-usage
        for author in item["authorships"]:
            if "author" not in author:
                continue
            if author["author"].get("display_name", None) is None:
                continue
            author_string = colrev.record.record_prep.PrepRecord.format_author_field(
                author["author"]["display_name"]
            )
            author_list.append(author_string)

        record_dict[Fields.AUTHOR] = " and ".join(author_list)

    def _parse_item_to_record(self, *, item: dict) -> colrev.record.record.Record:
        def set_entrytype(*, record_dict: dict, item: dict) -> None:
            # pylint: disable=colrev-missed-constant-usage
            if "title" in record_dict and record_dict["title"] is None:
                del record_dict["title"]
            if item.get("type_crossref", "") == "proceedings-article":
                record_dict[Fields.ENTRYTYPE] = "inproceedings"
                if (
                    item.get("primary_location", None) is not None
                    and item["primary_location"].get("source", None) is not None
                ):
                    display_name = item["primary_location"]["source"]["display_name"]
                    if display_name != "Proceedings":
                        record_dict[Fields.BOOKTITLE] = display_name
            elif item["type"] in ["journal-article", "article"]:
                record_dict[Fields.ENTRYTYPE] = "article"
                if (
                    item.get("primary_location", None) is not None
                    and item["primary_location"].get("source", None) is not None
                ):
                    record_dict[Fields.JOURNAL] = item["primary_location"]["source"][
                        "display_name"
                    ]
            else:
                record_dict[Fields.ENTRYTYPE] = "misc"

        record_dict = {}
        record_dict["id"] = item["id"].replace("https://openalex.org/", "")
        # pylint: disable=colrev-missed-constant-usage
        if "title" in item and item["title"] is not None:
            record_dict[Fields.TITLE] = item["title"].lstrip("[").rstrip("].")
        set_entrytype(record_dict=record_dict, item=item)

        if "publication_year" in item and item["publication_year"] is not None:
            record_dict[Fields.YEAR] = str(item["publication_year"])
        # pylint: disable=colrev-missed-constant-usage
        if "language" in item and item["language"] is not None:
            record_dict[Fields.LANGUAGE] = item["language"]

        if "is_retracted" in item and item["is_retracted"]:
            record_dict[FieldValues.RETRACTED] = item["is_retracted"]

        # pylint: disable=colrev-missed-constant-usage
        if "doi" in item and item["doi"] is not None:
            record_dict[Fields.DOI] = (
                item["doi"].upper().replace("HTTPS://DOI.ORG/", "")
            )

        record_dict[Fields.CITED_BY] = item["cited_by_count"]

        # pylint: disable=colrev-missed-constant-usage
        if "volume" in item["biblio"] and item["biblio"]["volume"] is not None:
            record_dict[Fields.VOLUME] = item["biblio"]["volume"]
        if "issue" in item["biblio"] and item["biblio"]["issue"] is not None:
            record_dict[Fields.NUMBER] = item["biblio"]["issue"]
        if "first_page" in item["biblio"] and item["biblio"]["first_page"] is not None:
            record_dict[Fields.PAGES] = item["biblio"]["first_page"]
        if "last_page" in item["biblio"] and item["biblio"]["last_page"] is not None:
            record_dict[Fields.PAGES] += "--" + item["biblio"]["last_page"]

        self._set_author_from_item(record_dict=record_dict, item=item)
        record = colrev.record.record.Record(record_dict)

        self._fix_errors(record=record)
        return record

    def _fix_errors(self, *, record: colrev.record.record.Record) -> None:
        if "PubMed" == record.data.get(Fields.JOURNAL, ""):
            record.remove_field(key=Fields.JOURNAL)
        try:
            self.language_service.unify_to_iso_639_3_language_codes(record=record)
        except colrev_exceptions.InvalidLanguageCodeException:
            record.remove_field(key=Fields.LANGUAGE)

    def _get_masterdata_record(
        self, *, record: colrev.record.record.Record
    ) -> colrev.record.record.Record:
        try:
            retrieved_record = self._parse_item_to_record(
                item=Works()[record.data["colrev.open_alex.id"]]
            )

            self.open_alex_lock.acquire(timeout=120)

            # Note : need to reload file because the object is not shared between processes
            open_alex_feed = self.search_source.get_api_feed(
                review_manager=self.review_manager,
                source_identifier=self.source_identifier,
                update_only=False,
                prep_mode=True,
            )

            open_alex_feed.add_update_record(retrieved_record)
            record.change_entrytype(
                new_entrytype=retrieved_record.data[Fields.ENTRYTYPE],
                qm=self.review_manager.get_qm(),
            )

            record.merge(
                retrieved_record,
                default_source=retrieved_record.data[Fields.ORIGIN][0],
            )
            open_alex_feed.save()
        except (
            colrev_exceptions.RecordNotParsableException,
            requests.exceptions.RequestException,
        ):
            pass
        except Exception as exc:
            raise exc
        finally:
            try:
                self.open_alex_lock.release()
            except ValueError:
                pass

        return record

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 30,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from OpenAlex based on similarity with the record provided"""

        if "colrev.open_alex.id" not in record.data:
            # Note: not yet implemented
            # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
            # if len(record.data.get(Fields.TITLE, "")) < 35 and Fields.DOI not in record.data:
            #     return record
            # record = self._check_doi_masterdata(record=record)
            return record

        record = self._get_masterdata_record(record=record)

        return record

    def search(self, rerun: bool) -> None:
        """Run a search of OpenAlex"""

        # https://docs.openalex.org/api-entities/works

        # crossref_feed = self.search_source.get_api_feed(
        #     review_manager=search_operation.review_manager,
        #     source_identifier=self.source_identifier,
        #     update_only=(not rerun),
        # )

        # try:
        #     if self.search_source.search_type == SearchType.MD:
        #         self._run_md_search_update(
        #             search_operation=search_operation,
        #             crossref_feed=crossref_feed,
        #         )
        #     elif self.search_source.search_type == SearchType.API:
        #         self._run_parameter_search(
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
        #             self._availability_exception_message
        #         )
        #     raise colrev_exceptions.ServiceNotAvailableException(
        #         self._availability_exception_message
        #     )

        # if self.search_source.search_type == SearchType.DB:
        #     if self.review_manager.in_ci_environment():
        #         raise colrev_exceptions.SearchNotAutomated(
        #             "DB search for OpenAlex not automated."
        #         )

        raise NotImplementedError

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for OpenAlex"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        raise colrev_exceptions.PackageParameterError(
            f"Cannot add OpenAlex endpoint with query {params}"
        )

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                logger=self.review_manager.logger,
            )
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for OpenAlex"""

        return record
