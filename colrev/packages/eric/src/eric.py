#! /usr/bin/env python
"""SearchSource: ERIC"""
from __future__ import annotations

import typing
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class ERICSearchSource(JsonSchemaMixin):
    """ERIC API"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "ID"
    search_types = [SearchType.API]
    endpoint = "colrev.eric"

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.oni
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/search_sources/eric.md"
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
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
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
                search_type=SearchType.OTHER,
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
    def _search_split(cls, search: str) -> str:
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
        params: str,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a)"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        # all API searches

        if len(params_dict) == 0:
            search_source = operation.create_db_source(
                search_source_cls=cls, params=params_dict
            )

        # pylint: disable=colrev-missed-constant-usage
        elif "https://api.ies.ed.gov/eric/?" in params_dict["url"]:
            url_parsed = urllib.parse.urlparse(params_dict["url"])
            new_query = urllib.parse.parse_qs(url_parsed.query)
            search = new_query.get("search", [""])[0]
            start = new_query.get("start", ["0"])[0]
            rows = new_query.get("rows", ["2000"])[0]
            if ":" in search:
                search = ERICSearchSource._search_split(search)
            filename = operation.get_unique_filename(file_path_string=f"eric_{search}")
            search_source = colrev.settings.SearchSource(
                endpoint=cls.endpoint,
                filename=filename,
                search_type=SearchType.API,
                search_parameters={"query": search, "start": start, "rows": rows},
                comment="",
            )

        else:
            raise colrev_exceptions.PackageParameterError(
                f"Cannot add ERIC endpoint with query {params_dict}"
            )

        operation.add_source_and_search(search_source)
        return search_source

    def get_query_return(self) -> typing.Iterator[colrev.record.record.Record]:
        """Get the records from a query"""
        full_url = self._build_search_url()

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
            record = self._create_record(doc)
            yield record

    def _run_api_search(
        self, *, eric_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        for record in self.get_query_return():
            eric_feed.add_update_record(record)

        eric_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of ERIC"""

        eric_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type == SearchType.API:
            self._run_api_search(eric_feed=eric_feed, rerun=rerun)
        else:
            raise NotImplementedError

    def _build_search_url(self) -> str:
        url = "https://api.ies.ed.gov/eric/"
        params = self.search_source.search_parameters
        query = params["query"]
        format_param = "json"
        start_param = params.get("start", "0")
        rows_param = params.get("rows", "2000")
        return f"{url}?search={query}&format={format_param}&start={start_param}&rows={rows_param}"

    def _create_record(self, doc: dict) -> colrev.record.record.Record:
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

        record = colrev.record.record.Record(record_dict)
        if Fields.LANGUAGE in record.data:
            try:
                record.data[Fields.LANGUAGE] = record.data[Fields.LANGUAGE][0]
                self.language_service.unify_to_iso_639_3_language_codes(record=record)
            except colrev_exceptions.InvalidLanguageCodeException:
                del record.data[Fields.LANGUAGE]
        return record

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    def _load_nbib(self) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            if "Journal Articles" in record_dict["PT"]:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            else:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

        def field_mapper(record_dict: dict) -> None:

            key_maps = {
                ENTRYTYPES.ARTICLE: {
                    "TI": Fields.TITLE,
                    "AU": Fields.AUTHOR,
                    "DP": Fields.YEAR,
                    "JT": Fields.JOURNAL,
                    "VI": Fields.VOLUME,
                    "IP": Fields.NUMBER,
                    "PG": Fields.PAGES,
                    "AB": Fields.ABSTRACT,
                    "AID": Fields.DOI,
                    "ISSN": Fields.ISSN,
                    "OID": f"{self.endpoint}.eric_id",
                    "OT": Fields.KEYWORDS,
                    "LA": Fields.LANGUAGE,
                    "PT": "type",
                    "LID": f"{self.endpoint}.eric_url",
                }
            }

            key_map = key_maps[record_dict[Fields.ENTRYTYPE]]
            for ris_key in list(record_dict.keys()):
                if ris_key in key_map:
                    standard_key = key_map[ris_key]
                    record_dict[standard_key] = record_dict.pop(ris_key)

            if Fields.AUTHOR in record_dict and isinstance(
                record_dict[Fields.AUTHOR], list
            ):
                record_dict[Fields.AUTHOR] = " and ".join(record_dict[Fields.AUTHOR])
            if Fields.EDITOR in record_dict and isinstance(
                record_dict[Fields.EDITOR], list
            ):
                record_dict[Fields.EDITOR] = " and ".join(record_dict[Fields.EDITOR])
            if Fields.KEYWORDS in record_dict and isinstance(
                record_dict[Fields.KEYWORDS], list
            ):
                record_dict[Fields.KEYWORDS] = ", ".join(record_dict[Fields.KEYWORDS])

            record_dict.pop("type", None)
            record_dict.pop("OWN", None)
            record_dict.pop("SO", None)

            for key, value in record_dict.items():
                record_dict[key] = str(value)

        records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            unique_id_field="OID",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=self.review_manager.logger,
        )

        return records

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".nbib":
            return self._load_nbib()

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
        """Source-specific preparation for ERIC"""

        if Fields.ISSN in record.data:
            record.data[Fields.ISSN] = record.data[Fields.ISSN].lstrip("ISSN-")

        return record
