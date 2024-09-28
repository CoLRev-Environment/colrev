#! /usr/bin/env python
"""API for Unpaywall"""
from __future__ import annotations

import re
import typing

import requests

import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.env.environment_manager import EnvironmentManager
from colrev.packages.unpaywall.src import utils


ENTRYTYPE_MAPPING = {
    "journal-article": ENTRYTYPES.ARTICLE,
    "book": ENTRYTYPES.BOOK,
    "proceedings-article": ENTRYTYPES.INPROCEEDINGS,
    "book-chapter": ENTRYTYPES.INBOOK,
    "conference": ENTRYTYPES.CONFERENCE,
    "dissertation": ENTRYTYPES.PHDTHESIS,
    "report": ENTRYTYPES.TECHREPORT,
    "other": ENTRYTYPES.MISC,
    "book-section": ENTRYTYPES.INBOOK,
    "monograph": ENTRYTYPES.THESIS,
    "report-component": ENTRYTYPES.TECHREPORT,
    "peer-review": ENTRYTYPES.MISC,
    "book-track": ENTRYTYPES.INCOLLECTION,
    "book-part": ENTRYTYPES.INBOOK,
    "journal-volume": ENTRYTYPES.ARTICLE,
    "book-set": ENTRYTYPES.MISC,
    "reference-entry": ENTRYTYPES.MISC,
    "journal": ENTRYTYPES.MISC,
    "component": ENTRYTYPES.MISC,
    "proceedings-series": ENTRYTYPES.PROCEEDINGS,
    "report-series": ENTRYTYPES.TECHREPORT,
    "proceedings": ENTRYTYPES.PROCEEDINGS,
    "database": ENTRYTYPES.MISC,
    "standard": ENTRYTYPES.MISC,
    "reference-book": ENTRYTYPES.BOOK,
    "posted-content": ENTRYTYPES.MISC,
    "journal-issue": ENTRYTYPES.MISC,
    "grant": ENTRYTYPES.MISC,
    "dataset": ENTRYTYPES.MISC,
    "book-series": ENTRYTYPES.BOOK,
    "edited-book": ENTRYTYPES.BOOK,
}


class UnpaywallAPI:
    """API for Unpaywall"""

    def __init__(self, search_parameters: dict) -> None:
        self.search_parameters = search_parameters

    def _get_authors(self, article: dict) -> typing.List[str]:
        authors = []
        z_authors = article.get("z_authors", [])
        if z_authors:
            for author in z_authors:
                given_name = author.get("given", "")
                family_name = author.get("family", "")
                if given_name and family_name:
                    authors.append(f"{family_name}, {given_name}")
        return authors

    def _get_affiliation(self, article: dict) -> typing.List[str]:
        affiliations = set()
        z_authors = article.get("z_authors", "")
        if z_authors:
            for person in z_authors:
                person_affiliation = person.get("affiliation", [])
                if person_affiliation:
                    affiliations.add(person_affiliation[0]["name"])

        return list(affiliations)

    def create_record(self, article: dict) -> colrev.record.record.Record:
        """Build record"""
        doi = article.get("doi", "").upper()
        record_dict = {Fields.ID: doi}

        entrytype = ENTRYTYPE_MAPPING.get(
            article.get("genre", "other"), ENTRYTYPES.MISC
        )
        record_dict[Fields.ENTRYTYPE] = entrytype

        record_dict[Fields.AUTHOR] = " and ".join(self._get_authors(article))
        record_dict[Fields.TITLE] = article.get("title", "")
        record_dict[Fields.YEAR] = article.get("year", "")
        record_dict[Fields.DOI] = doi

        if entrytype == ENTRYTYPES.ARTICLE:
            record_dict[Fields.JOURNAL] = article.get("journal_name", "")
        elif entrytype == ENTRYTYPES.BOOK:
            record_dict[Fields.PUBLISHER] = article.get("publisher", "")
        elif entrytype == ENTRYTYPES.INPROCEEDINGS:
            record_dict[Fields.BOOKTITLE] = article.get("journal_name", "")
        elif entrytype == ENTRYTYPES.INBOOK:
            record_dict[Fields.BOOKTITLE] = article.get("journal_name", "")
            record_dict[Fields.PUBLISHER] = article.get("publisher", "")
        elif entrytype == ENTRYTYPES.CONFERENCE:
            record_dict[Fields.BOOKTITLE] = article.get("journal_name", "")
        elif entrytype == ENTRYTYPES.PHDTHESIS:
            record_dict[Fields.SCHOOL] = ",".join(self._get_affiliation(article))
        elif entrytype == ENTRYTYPES.TECHREPORT:
            record_dict[Fields.INSTITUTION] = ",".join(self._get_affiliation(article))
        elif entrytype == ENTRYTYPES.INCOLLECTION:
            record_dict[Fields.BOOKTITLE] = article.get("journal_name", "")
            record_dict[Fields.PUBLISHER] = article.get("publisher", "")

        bestoa = article.get("best_oa_location", "")
        if bestoa:
            record_dict[Fields.URL] = bestoa.get("url_for_landing_page", "")
            record_dict[Fields.FULLTEXT] = bestoa.get("url_for_pdf", "")

        final_record_dict = {key: value for key, value in record_dict.items() if value}

        record = colrev.record.record.Record(final_record_dict)

        return record

    def get_query_records(self) -> typing.Iterator[colrev.record.record.Record]:
        """Get the records from a query"""
        all_results = []
        page = 1
        results_per_page = 50

        while True:
            page_dependend_url = self._build_search_url(page)
            response = requests.get(page_dependend_url, timeout=90)
            if response.status_code != 200:
                print(f"Error fetching data: {response.status_code}")
                return

            data = response.json()
            if "results" not in data:
                raise colrev_exceptions.ServiceNotAvailableException(
                    f"Could not reach API. Status Code: {response.status_code}"
                )

            new_results = data["results"]
            for result in new_results:
                if result not in all_results:
                    all_results.append(result)

            if len(new_results) < results_per_page:
                break

            page += 1

        for result in all_results:
            article = result["response"]
            record = self.create_record(article)
            yield record

    def _build_search_url(self, page: int) -> str:
        url = "https://api.unpaywall.org/v2/search?"
        params = self.search_parameters
        query = self._encode_query_for_html_url(params["query"])
        is_oa = params.get("is_oa", "null")
        email_param = params.get("email", "")

        if email_param and page == 1:

            env_man = EnvironmentManager()
            path = utils.UNPAYWALL_EMAIL_PATH
            value_string = email_param
            print(f"Updating registry settings:\n{path} = {value_string}")
            env_man.update_registry(path, value_string)

        email = utils.get_email()

        return f"{url}query={query}&is_oa={is_oa}&page={page}&email={email}"

    @classmethod
    def decode_html_url_encoding_to_string(cls, query: str) -> str:
        """Decode URL encoding to string"""
        query = query.replace("AND", "%20")
        query = re.sub(r"(%20)+", "%20", query).strip()
        query = query.replace("%20OR%20", " OR ")
        query = query.replace("%20-", " NOT ")
        query = query.replace(" -", " NOT ")
        query = query.replace("%20", " AND ")
        query = re.sub(r"\s+", " ", query).strip()
        query = query.lstrip(" ")
        query = query.rstrip(" ")
        query = query.replace("%22", '"')
        return query

    def _encode_query_for_html_url(self, query: str) -> str:
        query = query.replace("'", '"')
        query = re.sub(r"\s+", " ", query).strip()
        splited_query = query.split(" ")
        is_in_quotes = False
        parts = []
        for query_part in splited_query:
            if not is_in_quotes and query_part.startswith('"'):
                parts.append(query_part)
                is_in_quotes = True
            elif is_in_quotes and query_part.endswith('"'):
                parts.append(query_part)
                is_in_quotes = False
            elif is_in_quotes:
                parts.append(query_part)
            else:
                query_part = query_part.replace("OR", "%20OR%20")
                query_part = query_part.replace("NOT", "%20-")
                query_part = query_part.replace("AND", "%20")
                query_part = query_part.replace(" ", "%20")
                parts.append(query_part)
        joined_query = "%20".join(parts)
        joined_query = re.sub(r"(%20)+", "%20", joined_query).strip()
        joined_query = joined_query.replace("-%20", "-")
        return joined_query
