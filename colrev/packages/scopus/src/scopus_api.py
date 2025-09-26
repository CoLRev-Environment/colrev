#! /usr/bin/env python
"""Scopus API helper module."""
from __future__ import annotations

import logging
import os
import time
import typing
import urllib.parse

import requests

import colrev.record.record_prep
from colrev.constants import Fields
from colrev.packages.scopus.src import transformer


class ScopusAPIError(Exception):
    """Scopus API error."""


class ScopusAPI:
    """Wrapper around the Scopus and Crossref endpoints used by the package."""

    _SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
    _SCOPUS_ABSTRACT_BY_EID_URL = "https://api.elsevier.com/content/abstract/eid/"
    _CROSSREF_WORKS_URL = "https://api.crossref.org/works/"
    _THROTTLE_S = 0.34

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def _scopus_headers() -> dict:
        api_key = os.getenv("SCOPUS_API_KEY")
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-ELS-APIKey"] = api_key
        return headers

    @staticmethod
    def _crossref_headers() -> dict:
        return {
            "User-Agent": "colrev-scopus-author-resolution/1.0",
            "Accept": "application/json",
        }

    @staticmethod
    def has_api_key() -> bool:
        """Check if the SCOPUS_API_KEY environment variable is set."""
        return bool(os.getenv("SCOPUS_API_KEY"))

    def _scopus_abstract_authors_by_eid(
        self, *, eid: str
    ) -> list[dict[str, typing.Optional[str]]]:
        """Retrieve authors (names + ids) from the Scopus abstract endpoint."""

        url = self._SCOPUS_ABSTRACT_BY_EID_URL + urllib.parse.quote(eid)
        response = requests.get(
            url,
            headers=self._scopus_headers(),
            timeout=30,
            params={"field": "authors"},
        )
        response.raise_for_status()
        data = response.json()
        arr = (
            data.get("abstracts-retrieval-response", {})
            .get("authors", {})
            .get("author", [])
        )
        if not isinstance(arr, list):
            arr = [arr] if arr else []
        out: list[dict[str, typing.Optional[str]]] = []
        for author in arr:
            if not isinstance(author, dict):
                continue
            auid = author.get("@auid")
            preferred = author.get("preferred-name") or {}
            if not isinstance(preferred, dict):
                preferred = {}
            given = preferred.get("ce:given-name") or author.get("ce:given-name")
            family = preferred.get("ce:surname") or author.get("ce:surname")
            name = " ".join([part for part in [given, family] if part])
            out.append({"name": name if name else None, "scopus_author_id": auid})
        return out

    def _crossref_authors_by_doi(
        self, *, doi: str
    ) -> list[dict[str, typing.Optional[str]]]:
        """Retrieve authors (names only) from Crossref as a fallback."""

        url = self._CROSSREF_WORKS_URL + urllib.parse.quote(doi)
        response = requests.get(url, headers=self._crossref_headers(), timeout=30)
        response.raise_for_status()
        message = response.json().get("message", {})
        authors = message.get("author", []) or []
        out: list[dict[str, typing.Optional[str]]] = []
        for author in authors:
            if not isinstance(author, dict):
                continue
            given = author.get("given")
            family = author.get("family")
            name = " ".join([part for part in [given, family] if part])
            out.append({"name": name if name else None, "scopus_author_id": None})
        return out

    def resolve_authors(
        self, *, eid: typing.Optional[str], doi: typing.Optional[str]
    ) -> tuple[str, list[dict[str, typing.Optional[str]]]]:
        """Resolve authors using Scopus Abstract Retrieval first, then Crossref."""

        if eid:
            try:
                authors = self._scopus_abstract_authors_by_eid(eid=eid)
                time.sleep(self._THROTTLE_S)
                if authors:
                    return "scopus_abstract_retrieval", authors
            except requests.HTTPError:
                pass

        if doi:
            authors = self._crossref_authors_by_doi(doi=doi)
            time.sleep(self._THROTTLE_S)
            if authors:
                return "crossref", authors

        return "none", []

    @staticmethod
    def _looks_like_single_author(author_field: str | None) -> bool:
        if not author_field:
            return True
        return " and " not in author_field.strip()

    @staticmethod
    def _names_to_bibtex_and(names: list[str]) -> str:
        converted = []
        for name in names:
            name = (name or "").strip()
            if not name:
                continue
            parts = name.split()
            if len(parts) >= 2:
                family = parts[-1]
                given = " ".join(parts[:-1])
                converted.append(f"{family}, {given}")
            else:
                converted.append(name)
        return " and ".join(converted)

    def _records_from_entries(
        self, entries: list
    ) -> typing.Iterator[colrev.record.record_prep.PrepRecord]:
        for entry in entries:
            record_dict = transformer.transform_record(entry)

            eid = entry.get("eid") or record_dict.get("scopus.eid")
            doi = entry.get("prism:doi") or record_dict.get("doi")

            _, authors = self.resolve_authors(eid=eid, doi=doi)

            names: list[str] = [
                name
                for author in authors
                if isinstance((name := author.get("name")), str) and name
            ]
            if names and self._looks_like_single_author(record_dict.get(Fields.AUTHOR)):
                record_dict[Fields.AUTHOR] = self._names_to_bibtex_and(names)

            yield colrev.record.record_prep.PrepRecord(record_dict)

    def iter_records(
        self, *, query: str
    ) -> typing.Iterator[colrev.record.record_prep.PrepRecord]:
        """Iterate over records from the Scopus Search API for the given query."""
        params = {
            "query": query,
            "count": 10,
            "start": 0,
            "view": "STANDARD",
        }

        response = requests.get(
            self._SCOPUS_SEARCH_URL,
            headers=self._scopus_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            self.logger.info("API Error: %s — %s", response.status_code, response.text)

        data = response.json()
        entries = data.get("search-results", {}).get("entry", []) or []
        self.logger.info("Found %d results via API", len(entries))

        yield from self._records_from_entries(entries)
