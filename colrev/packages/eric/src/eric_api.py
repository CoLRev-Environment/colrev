#! /usr/bin/env python
"""ERIC API."""

import typing

import requests

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class ERICAPI:
    """Connector for the ERIC API."""

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

    def __init__(self, params: dict) -> None:
        """Initialize the instance."""
        self.params = params
        self.language_service = colrev.env.language_service.LanguageService()

    def _build_search_url(self) -> str:
        url = "https://api.ies.ed.gov/eric/"
        query = self.params["query"]
        format_param = "json"
        start_param = self.params.get("start", "0")
        rows_param = self.params.get("rows", "2000")
        return f"{url}?search={query}&format={format_param}&start={start_param}&rows={rows_param}"

    def _build_base_record_dict(self, doc: dict) -> dict:
        record_dict = {Fields.ID: doc["id"], Fields.ENTRYTYPE: "other"}
        publicationtype = doc.get("publicationtype", [])
        if "Journal Articles" in publicationtype:
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
        elif "Books" in publicationtype:
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.BOOK
        return record_dict

    def _add_api_fields(self, *, record_dict: dict, doc: dict) -> None:
        for field in self.API_FIELDS:
            field_value = doc.get(field)
            if field_value is not None:
                record_dict[field] = field_value

    def _map_api_fields(self, *, record_dict: dict) -> None:
        for api_field, rec_field in self.FIELD_MAPPING.items():
            if api_field not in record_dict:
                continue
            record_dict[rec_field] = record_dict.pop(api_field)

    def _add_source_fields(self, *, record_dict: dict, doc: dict) -> None:
        if "source" in doc:
            record_dict[Fields.JOURNAL] = doc.pop("source")

    def _normalize_core_fields(self, *, record_dict: dict) -> None:
        if "subject" in record_dict:
            record_dict["subject"] = ", ".join(record_dict["subject"])
        if Fields.AUTHOR in record_dict:
            # pylint: disable=colrev-missed-constant-usage
            record_dict[Fields.AUTHOR] = " and ".join(record_dict["author"])
        if Fields.YEAR in record_dict:
            # pylint: disable=colrev-missed-constant-usage
            record_dict[Fields.YEAR] = str(record_dict["year"])

    def _normalize_identifier_fields(self, *, record_dict: dict) -> None:
        if Fields.ISSN in record_dict:
            # pylint: disable=colrev-missed-constant-usage
            record_dict[Fields.ISSN] = record_dict["issn"][0].lstrip("EISSN-")
        if Fields.ISBN in record_dict:
            # pylint: disable=colrev-missed-constant-usage
            record_dict[Fields.ISBN] = record_dict["isbn"][0].lstrip("ISBN-")

    def _normalize_language(self, *, record: colrev.record.record.Record) -> None:
        if Fields.LANGUAGE in record.data:
            try:
                record.data[Fields.LANGUAGE] = record.data[Fields.LANGUAGE][0]
                self.language_service.unify_to_iso_639_3_language_codes(record=record)
            except colrev_exceptions.InvalidLanguageCodeException:
                del record.data[Fields.LANGUAGE]

    def _create_record(self, doc: dict) -> colrev.record.record.Record:
        record_dict = self._build_base_record_dict(doc=doc)
        self._add_api_fields(record_dict=record_dict, doc=doc)
        self._map_api_fields(record_dict=record_dict)
        self._add_source_fields(record_dict=record_dict, doc=doc)
        self._normalize_core_fields(record_dict=record_dict)
        self._normalize_identifier_fields(record_dict=record_dict)
        record = colrev.record.record.Record(record_dict)
        self._normalize_language(record=record)
        return record

    def get_query_return(self) -> typing.Iterator[colrev.record.record.Record]:
        """Get the records from a query."""
        full_url = self._build_search_url()

        response = requests.get(full_url, timeout=90)
        if response.status_code != 200:
            return
        # with open("test.json", "wb") as file:
        #     file.write(response.content)
        data = response.json()

        if "docs" not in data["response"]:
            raise colrev_exceptions.ServiceNotAvailableException(
                "Could not reach API. Status Code: " + response.status_code
            )

        for doc in data["response"]["docs"]:
            record = self._create_record(doc)
            yield record
