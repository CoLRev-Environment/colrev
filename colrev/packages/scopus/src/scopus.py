#! /usr/bin/env python
"""SearchSource: Scopus"""
from __future__ import annotations

import logging
import os
import time
import typing
import urllib.parse
from pathlib import Path

import requests
from pydantic import Field

import colrev.loader.bib
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.scopus.src import transformer


class ScopusSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Scopus"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.scopus"
    source_identifier = "scopus.eid"
    search_types = [SearchType.DB, SearchType.API]
    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "https://www.scopus.com/search/form.uri?display=advanced"

    # --- External API endpoints ---
    _SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
    _SCOPUS_ABSTRACT_BY_EID_URL = "https://api.elsevier.com/content/abstract/eid/"
    _CROSSREF_WORKS_URL = "https://api.crossref.org/works/"

    # Throttling to be gentle with APIs
    _THROTTLE_S = 0.34

    def __init__(
        self, *, source_operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.review_manager = source_operation.review_manager
        self.search_source = self.settings_class(**settings)
        self.quality_model = self.review_manager.get_qm()
        self.operation = source_operation

    # ------------------------
    # Author-resolution helpers
    # ------------------------
    def _scopus_headers(self) -> dict:
        api_key = os.getenv("SCOPUS_API_KEY")
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-ELS-APIKey"] = api_key
        return headers

    def _crossref_headers(self) -> dict:
        return {
            "User-Agent": "colrev-scopus-author-resolution/1.0",
            "Accept": "application/json",
        }

    def _scopus_abstract_authors_by_eid(
        self, *, eid: str
    ) -> list[dict[str, typing.Optional[str]]]:
        """Return [{'name': 'Given Family', 'scopus_author_id': '...'}, ...]
        via Abstract Retrieval."""
        url = self._SCOPUS_ABSTRACT_BY_EID_URL + urllib.parse.quote(eid)
        r = requests.get(
            url,
            headers=self._scopus_headers(),
            timeout=30,
            params={"field": "authors"},
        )
        r.raise_for_status()
        data = r.json()
        arr = (
            data.get("abstracts-retrieval-response", {})
            .get("authors", {})
            .get("author", [])
        )
        if not isinstance(arr, list):
            arr = [arr] if arr else []
        out: list[dict[str, typing.Optional[str]]] = []
        for a in arr:
            if not isinstance(a, dict):
                continue
            auid = a.get("@auid")
            pref = a.get("preferred-name") or {}
            if not isinstance(pref, dict):
                pref = {}
            given = pref.get("ce:given-name") or a.get("ce:given-name")
            family = pref.get("ce:surname") or a.get("ce:surname")
            name = " ".join([p for p in [given, family] if p])
            out.append({"name": name if name else None, "scopus_author_id": auid})
        return out

    def _crossref_authors_by_doi(
        self, *, doi: str
    ) -> list[dict[str, typing.Optional[str]]]:
        """Return [{'name': 'Given Family', 'scopus_author_id': None}, ...] via Crossref."""
        url = self._CROSSREF_WORKS_URL + urllib.parse.quote(doi)
        r = requests.get(url, headers=self._crossref_headers(), timeout=30)
        r.raise_for_status()
        msg = r.json().get("message", {})
        authors = msg.get("author", []) or []
        out: list[dict[str, typing.Optional[str]]] = []
        for a in authors:
            if not isinstance(a, dict):
                continue
            given = a.get("given")
            family = a.get("family")
            name = " ".join([p for p in [given, family] if p])
            out.append({"name": name if name else None, "scopus_author_id": None})
        return out

    def _resolve_authors(
        self, *, eid: typing.Optional[str], doi: typing.Optional[str]
    ) -> tuple[str, list[dict[str, typing.Optional[str]]]]:
        """
        Try Scopus Abstract Retrieval first (IDs + names), then Crossref (names only).
        Returns (source, authors).
        """
        # 1) Scopus Abstract Retrieval
        if eid:
            try:
                authors = self._scopus_abstract_authors_by_eid(eid=eid)
                time.sleep(self._THROTTLE_S)
                if authors:
                    return "scopus_abstract_retrieval", authors
            except requests.HTTPError:
                pass

        # 2) Crossref fallback (no Scopus IDs)
        if doi:
            authors = self._crossref_authors_by_doi(doi=doi)
            time.sleep(self._THROTTLE_S)
            if authors:
                return "crossref", authors

        return "none", []

    @staticmethod
    def _looks_like_single_author(author_field: str | None) -> bool:
        """Heuristic: treat empty or single 'and'-less string as single author."""
        if not author_field:
            return True
        return " and " not in author_field.strip()

    @staticmethod
    def _names_to_bibtex_and(names: list[str]) -> str:
        """
        Convert ['Given Family', 'Given2 Family2'] -> 'Family, Given and Family2, Given2'
        (best-effort; falls back to provided order if splitting is unclear).
        """
        converted = []
        for n in names:
            n = (n or "").strip()
            if not n:
                continue
            parts = n.split()
            if len(parts) >= 2:
                family = parts[-1]
                given = " ".join(parts[:-1])
                converted.append(f"{family}, {given}")
            else:
                converted.append(n)
        return " and ".join(converted)

    # ------------------------
    # API search + integration
    # ------------------------
    def _simple_api_search(self, query: str, rerun: bool) -> None:

        api_key = os.getenv("SCOPUS_API_KEY")
        if not api_key:
            self.review_manager.logger.info(
                'No API key found. Set API key using: export SCOPUS_API_KEY="XXXXX"'
            )
            return

        scopus_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        try:
            params = {
                "query": query,
                "count": 10,
                "start": 0,
                "view": "STANDARD",  # STANDARD: only first author (with ID) in results
            }

            response = requests.get(
                self._SCOPUS_SEARCH_URL,
                headers=self._scopus_headers(),
                params=params,
                timeout=30,
            )

            if response.status_code != 200:
                self.review_manager.logger.info(
                    f"API Error: {response.status_code} — {response.text}"
                )

            data = response.json()
            entries = data.get("search-results", {}).get("entry", []) or []
            self.review_manager.logger.info(f"Found {len(entries)} results via API")

            for record in self._get_records_from_api(entries):
                scopus_feed.add_update_record(retrieved_record=record)

        except ValueError as e:
            self.review_manager.logger.info(f"API search error: {str(e)}")

        scopus_feed.save()

    def _get_records_from_api(
        self,
        entries: list,
    ) -> typing.Generator[colrev.record.record_prep.PrepRecord]:
        """
        Transform each Scopus entry to a CoLRev record and enrich with a resolved author list:
        - colrev.scopus.author_resolution_source
        - colrev.scopus.authors_json
        - Update 'author' field (BibTeX) if only single/empty author present
        """
        for entry in entries:
            rec = transformer.transform_record(entry)

            # Grab EID / DOI directly from the search entry
            eid = entry.get("eid") or rec.get("scopus.eid")  # transformer may set it
            doi = entry.get("prism:doi") or rec.get("doi")

            _, authors = self._resolve_authors(eid=eid, doi=doi)

            # Optionally update the human-readable BibTeX 'author' if it's empty/single
            names: list[str] = [
                n for a in authors if isinstance((n := a.get("name")), str) and n
            ]
            if names and self._looks_like_single_author(rec.get(Fields.AUTHOR)):
                rec[Fields.AUTHOR] = self._names_to_bibtex_and(names)

            yield colrev.record.record_prep.PrepRecord(rec)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0.0}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
        elif "www.scopus.com" in data:
            if data.count("www.scopus.com") >= data.count("\n@"):
                result["confidence"] = 1.0
        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
    ) -> colrev.settings.SearchSource:

        params_dict: dict = {}
        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.API:
            search_source = operation.create_api_source(endpoint=cls.endpoint)

        elif search_type == SearchType.DB:
            search_source = operation.create_db_source(
                search_source_cls=cls,
                params={},
            )

        operation.add_source_and_search(search_source)
        return search_source

    def search(self, rerun: bool) -> None:
        query = self.search_source.search_parameters.get("query", "")

        if not query:
            raise ValueError("No query provided. Use --query when adding source.")

        if self.search_source.search_type == SearchType.API:
            self.review_manager.logger.info(f"Running Scopus API search with: {query}")
            self._simple_api_search(query, rerun)
            return

        if self.search_source.search_type == SearchType.DB:
            self.operation.run_db_search(  # type: ignore
                search_source_cls=self.__class__,
                source=self.search_source,
            )
            return

        raise NotImplementedError

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        return record

    @classmethod
    def _load_bib(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            if "document_type" in record_dict:
                if record_dict["document_type"] == "Conference Paper":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
                elif record_dict["document_type"] == "Conference Review":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.PROCEEDINGS
                elif record_dict["document_type"] == "Article":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE

        def field_mapper(record_dict: dict) -> None:
            if record_dict[Fields.ENTRYTYPE] in [
                ENTRYTYPES.INPROCEEDINGS,
                ENTRYTYPES.PROCEEDINGS,
            ]:
                record_dict[Fields.BOOKTITLE] = record_dict.pop(Fields.JOURNAL, None)

            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK:
                if (
                    Fields.JOURNAL in record_dict
                    and Fields.BOOKTITLE not in record_dict
                ):
                    record_dict[Fields.BOOKTITLE] = record_dict.pop(Fields.TITLE, None)
                    record_dict[Fields.TITLE] = record_dict.pop(Fields.JOURNAL, None)

            if "art_number" in record_dict:
                record_dict[f"{cls.endpoint}.art_number"] = record_dict.pop(
                    "art_number"
                )
            if "note" in record_dict:
                record_dict[f"{cls.endpoint}.note"] = record_dict.pop("note")
            if "document_type" in record_dict:
                record_dict[f"{cls.endpoint}.document_type"] = record_dict.pop(
                    "document_type"
                )
            if "source" in record_dict:
                record_dict[f"{cls.endpoint}.source"] = record_dict.pop("source")

            if "Start_Page" in record_dict and "End_Page" in record_dict:
                if (
                    record_dict["Start_Page"] != "nan"
                    and record_dict["End_Page"] != "nan"
                ):
                    record_dict[Fields.PAGES] = (
                        record_dict["Start_Page"] + "--" + record_dict["End_Page"]
                    ).replace(".0", "")
                    del record_dict["Start_Page"]
                    del record_dict["End_Page"]

        colrev.loader.bib.run_fix_bib_file(filename, logger=logger)
        records = colrev.loader.load_utils.load(
            filename=filename,
            unique_id_field="ID",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
        )
        return records

    @classmethod
    def load(cls, *, filename: Path, logger: logging.Logger) -> dict:
        if filename.suffix == ".bib":
            return cls._load_bib(filename=filename, logger=logger)
        raise NotImplementedError

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        return record
