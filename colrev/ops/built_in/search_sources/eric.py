#! /usr/bin/env python
"""SearchSource: ERIC"""
from __future__ import annotations

import typing
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils_nbib
import colrev.ops.search
import colrev.record
from colrev.constants import Fields

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class ERICSearchSource(JsonSchemaMixin):
    """ERIC API"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "ID"
    search_types = [colrev.settings.SearchType.API]
    endpoint = "colrev.eric"

    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/eric.md"
    )
    short_name = "ERIC"

    API_FIELDS = [
        "title",
        "author",
        "source",
        "publicationdateyear",
        "description",
        "subject",
        "peerreviewed",
        "abstractor",
        "audience",
        "authorxlink",
        "e_datemodified",
        "e_fulltextauth",
        "e yearadded",
        "educationlevel",
        "identifiersgeo",
        "identifierslaw",
        "identifierstest",
        "iescited",
        "iesfunded",
        "iesgrantcontractnum",
        "iesgrantcontractnumxlink",
        "ieslinkpublication",
        "ieslinkwwcreviewguide",
        "ieswwcreviewed",
        "institution",
        "isbn",
        "issn",
        "language",
        "publisher",
        "sourceid",
        "sponsor",
        "url",
    ]
    FIELD_MAPPING = {"publicationdateyear": "year", "description": "abstract"}

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # ERIC as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint=self.endpoint,
                filename=Path("data/search/eric.bib"),
                search_type=colrev.settings.SearchType.OTHER,
                search_parameters={},
                comment="",
            )
        self.language_service = colrev.env.language_service.LanguageService()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ERIC"""

        result = {"confidence": 0.1}

        if "OWN - ERIC" in data:
            # if data.count("OWN - ERIC") > data.count("\n\n"):
            result["confidence"] = 1.0

        # Note : no features in bib file for identification

        return result

    @classmethod
    def __search_split(cls, search: str) -> str:
        if " AND " in search:
            search_parts = search.split(" AND ")
            field_values = []
            for part in search_parts:
                field, value = part.split(":")
                field = field.strip()
                value = value.strip().strip("'")
                field_value = f"{field}%3A%22{urllib.parse.quote(value)}%22"
                field_values.append(field_value)
            return " AND ".join(field_values)

        field, value = search.split(":")
        field = field.strip()
        value = value.strip().strip("'")
        field_value = f"{field}%3A%22{urllib.parse.quote(value)}%22"
        return field_value

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a)"""

        # all API searches

        if len(params) == 0:
            add_source = operation.add_db_source(search_source_cls=cls, params=params)
            return add_source

        # pylint: disable=colrev-missed-constant-usage
        if "https://api.ies.ed.gov/eric/?" in params["url"]:
            url_parsed = urllib.parse.urlparse(params["url"])
            new_query = urllib.parse.parse_qs(url_parsed.query)
            search = new_query.get("search", [""])[0]
            start = new_query.get("start", ["0"])[0]
            rows = new_query.get("rows", ["2000"])[0]
            if ":" in search:
                search = ERICSearchSource.__search_split(search)
            filename = operation.get_unique_filename(file_path_string=f"eric_{search}")
            add_source = colrev.settings.SearchSource(
                endpoint=cls.endpoint,
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters={"query": search, "start": start, "rows": rows},
                comment="",
            )
            return add_source

        raise colrev_exceptions.PackageParameterError(
            f"Cannot add ERIC endpoint with query {params}"
        )

    def get_query_return(self) -> typing.Iterator[colrev.record.Record]:
        """Get the records from a query"""
        full_url = self.__build_search_url()

        response = requests.get(full_url, timeout=90)
        if response.status_code != 200:
            return
        with open("test.json", "wb") as file:
            file.write(response.content)
        data = response.json()

        if "docs" not in data["response"]:
            raise colrev_exceptions.ServiceNotAvailableException(
                "Could not reach API. Status Code: " + response.status_code
            )

        for doc in data["response"]["docs"]:
            record = self.__create_record(doc)
            yield record

    def __run_api_search(
        self, *, eric_feed: colrev.ops.search_feed.GeneralOriginFeed, rerun: bool
    ) -> None:
        records = self.review_manager.dataset.load_records_dict()
        for record in self.get_query_return():
            prev_record_dict_version: dict = {}
            added = eric_feed.add_record(record=record)

            if added:
                self.review_manager.logger.info(" retrieve " + record.data[Fields.ID])
            else:
                eric_feed.update_existing_record(
                    records=records,
                    record_dict=record.data,
                    prev_record_dict_version=prev_record_dict_version,
                    source=self.search_source,
                    update_time_variant_fields=rerun,
                )

        eric_feed.print_post_run_search_infos(records=records)
        eric_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)

    def run_search(self, rerun: bool) -> None:
        """Run a search of ERIC"""

        eric_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type == colrev.settings.SearchType.API:
            self.__run_api_search(eric_feed=eric_feed, rerun=rerun)
        else:
            raise NotImplementedError

    def __build_search_url(self) -> str:
        url = "https://api.ies.ed.gov/eric/"
        params = self.search_source.search_parameters
        query = params["query"]
        format_param = "json"
        start_param = params.get("start", "0")
        rows_param = params.get("rows", "2000")
        return f"{url}?search={query}&format={format_param}&start={start_param}&rows={rows_param}"

    def __create_record(self, doc: dict) -> colrev.record.Record:
        # pylint: disable=too-many-branches
        record_dict = {Fields.ID: doc["id"]}
        record_dict[Fields.ENTRYTYPE] = "other"
        if "Journal Articles" in doc["publicationtype"]:
            record_dict[Fields.ENTRYTYPE] = "article"
        elif "Books" in doc["publicationtype"]:
            record_dict[Fields.ENTRYTYPE] = "book"

        for field in self.API_FIELDS:
            field_value = doc.get(field)
            if field_value is not None:
                record_dict[field] = field_value

        for api_field, rec_field in self.FIELD_MAPPING.items():
            if api_field not in record_dict:
                continue
            record_dict[rec_field] = record_dict.pop(api_field)

        if "source" in doc:
            record_dict[Fields.JOURNAL] = doc.pop("source")

        if "subject" in record_dict:
            record_dict["subject"] = ", ".join(record_dict["subject"])

        if Fields.AUTHOR in record_dict:
            # pylint: disable=colrev-missed-constant-usage
            record_dict[Fields.AUTHOR] = " and ".join(record_dict["author"])
        if Fields.ISSN in record_dict:
            # pylint: disable=colrev-missed-constant-usage
            record_dict[Fields.ISSN] = record_dict["issn"][0].lstrip("EISSN-")
        if Fields.ISBN in record_dict:
            # pylint: disable=colrev-missed-constant-usage
            record_dict[Fields.ISBN] = record_dict["isbn"][0].lstrip("ISBN-")

        if Fields.YEAR in record_dict:
            # pylint: disable=colrev-missed-constant-usage
            record_dict[Fields.YEAR] = str(record_dict["year"])

        record = colrev.record.Record(data=record_dict)
        if Fields.LANGUAGE in record.data:
            try:
                record.data[Fields.LANGUAGE] = record.data[Fields.LANGUAGE][0]
                self.language_service.unify_to_iso_639_3_language_codes(record=record)
            except colrev_exceptions.InvalidLanguageCodeException:
                del record.data[Fields.LANGUAGE]
        return record

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".nbib":
            nbib_loader = colrev.ops.load_utils_nbib.NBIBLoader(
                load_operation=load_operation,
                source=self.search_source,
                unique_id_field="eric_id",
            )
            entries = nbib_loader.load_nbib_entries()
            records = nbib_loader.convert_to_records(entries=entries)
            return records

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for ERIC"""

        if Fields.ISSN in record.data:
            record.data[Fields.ISSN] = record.data[Fields.ISSN].lstrip("ISSN-")

        return record
