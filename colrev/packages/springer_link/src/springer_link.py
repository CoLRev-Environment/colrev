#! /usr/bin/env python
"""SearchSource: Springer Link"""
from __future__ import annotations

import logging
import os
import re
import typing
import urllib.parse
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlparse

import inquirer
import pandas as pd
from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.search_file
import colrev.utils
from colrev.constants import Colors
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search
from colrev.packages.springer_link.src import springer_link_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code

DEFAULT_PAGE_SIZE = 10


class SpringerLinkSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Springer Link"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.springer_link"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [SearchType.DB, SearchType.API]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    SETTINGS = {
        "api_key": "packages.search_source.colrev.springer_link.api_key",
    }
    db_url = "https://link.springer.com/"

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

        self.language_service = colrev.env.language_service.LanguageService()
        self.api = springer_link_api.SpringerLinkAPI(
            session=colrev.utils.get_cached_session()
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Springer Link"""

        result = {"confidence": 0.0}

        if filename.suffix == ".csv":
            if data.count("http://link.springer.com") > data.count("\n") - 2:
                result["confidence"] = 1.0
                return result

        # Note : no features in bib file for identification

        return result

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict: dict = {}  # {params.split("=")[0]: params.split("=")[1]}
        search_type = colrev.utils.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.DB:
            search_source = create_db_source(
                path=path,
                platform=cls.endpoint,
                params=params_dict,
                add_to_git=True,
                logger=logger,
            )

        elif search_type == SearchType.API:
            search_source = create_api_source(platform=cls.endpoint, path=path)
            search_source.search_parameters = {"query": search_source.search_string}
            search_source.search_string = ""
            instance = cls(search_file=search_source)
            instance.api_ui()
            search_source.search_parameters = instance._add_constraints()

        else:
            raise NotImplementedError
        return search_source

    def search(self, rerun: bool) -> None:
        """Run a search of SpringerLink"""

        if self.search_source.search_type == SearchType.DB:
            run_db_search(
                db_url=self.db_url,
                source=self.search_source,
                add_to_git=True,
            )
            return

        if self.search_source.search_type == SearchType.API:
            springer_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                source_identifier=self.source_identifier,
                search_source=self.search_source,
                update_only=(not rerun),
                logger=self.logger,
                verbose_mode=self.verbose_mode,
            )
            self._run_api_search(springer_feed=springer_feed, rerun=rerun)
            return

        raise NotImplementedError

    def _add_constraints(self) -> dict:
        """Add constraints for API query."""
        complex_query_prompt = [
            inquirer.List(
                name="complex_query",
                message="Select how the search will be entered",
                choices=["interactively", "complete_search_string"],
            ),
        ]

        answers = inquirer.prompt(complex_query_prompt)

        if answers["complex_query"] == "complete_search_string":
            query = input("Please enter your search string: ")
            search_parameters = {"query": query}

        else:

            print(
                "Please enter your search parameter for the following constraints"
                + "(or just press enter to continue):"
            )
            search_string = input(
                "search string (e.g., 'keyword:digital AND keyword:outsourcing'): "
            )
            subject_choices = [
                inquirer.Checkbox(
                    name="subject",
                    message="Select subject(s) or press Enter to skip:",
                    choices=[
                        "Astronomy",
                        "Behavioral Sciences",
                        "Biomedical Sciences",
                        "Business and Management",
                        "Chemistry",
                        "Climate",
                        "Computer Science",
                        "Earth Sciences",
                        "Economics",
                        "Education and Language",
                        "Energy",
                        "Engineering",
                        "Environmental Sciences",
                        "Food Science and Nutrition",
                        "General Interest",
                        "Geography",
                        "Law",
                        "Life Sciences",
                        "Materials",
                        "Mathematics",
                        "Medicine",
                        "Philosophy",
                        "Physics",
                        "Public Health",
                        "Social Sciences",
                        "Statistics",
                        "Water",
                    ],
                ),
            ]
            answers = inquirer.prompt(subject_choices)
            subject = ",".join(answers["subject"])

            language_choices = [
                inquirer.Checkbox(
                    name="language",
                    message="Select language(s) or press Enter to skip:",
                    choices=[
                        "en",
                        "de",
                        "fr",
                        "es",
                        "it",
                        "pt",
                        "nl",
                    ],
                ),
            ]
            answers = inquirer.prompt(language_choices)
            language = ",".join(answers["language"])

            year_choices = [
                inquirer.Text(
                    name="year",
                    message="Select year(s) or press Enter to skip:",
                    validate=self._is_year,
                ),
            ]
            answers = inquirer.prompt(year_choices)
            year = answers["year"]

            doc_type_choices = [
                inquirer.Checkbox(
                    name="doc_type",
                    message="Select doc_type(s) or press Enter to skip:",
                    choices=["Journal", "Book"],
                ),
            ]
            answers = inquirer.prompt(doc_type_choices)
            doc_type = ",".join(answers["doc_type"])

            search_parameters = {
                "subject": subject,
                "search_string": search_string,
                "language": language,
                "year": year,
                "type": doc_type,
            }

        return search_parameters

    def build_query(self, search_parameters: dict) -> str:
        """Build API query."""

        if "query" in search_parameters:
            query = search_parameters["query"]

        else:
            constraints = []
            for key, value in search_parameters.items():
                if value == "":
                    continue

                if key in ["subject", "language", "doc_type"]:

                    subject_query = (
                        f'{key}:"'
                        + f'" OR {key}:"'.join(value for value in value.split(","))
                        + '"'
                    )
                    constraints.append(f"({subject_query})")
                    continue

                if key == "search_string":
                    constraints.append(value)
                    continue

                if value:
                    constraints.append(f'{key}:"{value}"')
                    continue

            query = " AND ".join(constraints)

        return urllib.parse.quote(query)

    def _build_api_search_url(
        self,
        query: str,
        api_key: str,
        start: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> str:
        # Include both start (s) and page size (p)
        return (
            "https://api.springernature.com/meta/v2/json"
            f"?q={query}&api_key={api_key}&s={start}&p={page_size}"
        )

    # pylint: disable=too-many-locals
    def get_query_return(self) -> typing.Iterator[colrev.record.record.Record]:
        """Get the records from an API search"""
        query = self.build_query(self.search_source.search_parameters)
        api_key = self.get_api_key()

        # Allow overriding via settings; fall back to DEFAULT_PAGE_SIZE
        page_size = int(
            self.search_source.search_parameters.get("page_size", DEFAULT_PAGE_SIZE)
        )
        start = int(self.search_source.search_parameters.get("start", 1))

        last_start = None  # to prevent infinite loops if API repeats nextPage

        while True:
            full_url = self._build_api_search_url(
                query=query, api_key=api_key, start=start, page_size=page_size
            )
            # print(full_url)

            try:
                data = self.api.get_json(full_url, timeout=10)
            except springer_link_api.SpringerLinkAPIError as exc:
                print(f"Error - API search failed for the following reason: {exc}")
                return

            records = data.get("records", [])
            if not records:
                break

            for record in records:
                yield self._create_record(record)

            # Prefer authoritative nextPage link when present
            next_page = data.get("nextPage")
            if next_page:
                # Parse s (and optionally p) from nextPage to be safe
                try:

                    qs = parse_qs(urlparse(next_page).query)
                    next_start = int(qs.get("s", [start + page_size])[0])
                    # Some responses also include "p" — keep it aligned if present
                    if "p" in qs:
                        page_size = int(qs["p"][0])
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    print(exc)
                    next_start = start + page_size
            else:
                # Fallback if no nextPage provided: advance by current page_size
                next_start = start + page_size

            # Stop if the API cycles or we’ve reached the end (short page)
            if next_start == last_start or len(records) < page_size:
                break

            last_start = start
            start = next_start

    def _run_api_search(
        self, springer_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        """Save API search results."""
        for record in self.get_query_return():
            springer_feed.add_update_record(record)

        springer_feed.save()

    def _create_record(self, doc: dict) -> colrev.record.record.Record:
        """Fieldmapper API search"""
        record_dict = {Fields.ID: doc["identifier"]}
        record_dict[Fields.ENTRYTYPE] = "misc"

        if "Article" in doc["contentType"]:
            record_dict[Fields.ENTRYTYPE] = "article"
        elif "Chapter" in doc["contentType"]:
            record_dict[Fields.ENTRYTYPE] = "inproceedings"
        elif "Book" in doc["contentType"]:
            record_dict[Fields.ENTRYTYPE] = "book"

        record_dict.update(
            {
                Fields.AUTHOR: " and ".join(
                    creator.get("creator", "") for creator in doc.get("creators", [])
                ),
                Fields.TITLE: doc.get("title", ""),
                Fields.PUBLISHER: doc.get("publisher", ""),
                Fields.BOOKTITLE: (
                    doc.get("publicationName", "")
                    if doc.get("publicationType") == "Book"
                    else ""
                ),
                Fields.JOURNAL: (
                    doc.get("publicationName", "")
                    if doc.get("publicationType") == "Journal"
                    else ""
                ),
                Fields.YEAR: (
                    doc.get("publicationDate", "").split("-")[0]
                    if doc.get("publicationDate")
                    else ""
                ),
                Fields.VOLUME: doc.get("volume", ""),
                Fields.NUMBER: doc.get("number", ""),
                Fields.PAGES: (
                    f"{doc.get('startingPage', '')}-{doc.get('endingPage', '')}"
                    if doc.get("startingPage") and doc.get("endingPage")
                    else ""
                ),
                Fields.DOI: doc.get("doi", ""),
                Fields.URL: next(
                    (
                        url.get("value", "")
                        for url in doc.get("url", [])
                        if url.get("format") == "html"
                    ),
                    doc.get("url", [{}])[0].get("value", "") if doc.get("url") else "",
                ),
            }
        )

        record = colrev.record.record.Record(data=record_dict)
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

    @classmethod
    def _load_csv(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            if record_dict["Content Type"] == "Article":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            elif record_dict["Content Type"] == "Book":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.BOOK
            elif record_dict["Content Type"] == "Chapter":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INBOOK
            else:
                record_dict[Fields.ENTRYTYPE] = "misc"

        def field_mapper(record_dict: dict) -> None:
            record_dict[Fields.TITLE] = record_dict.pop("Item Title", "")
            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
                record_dict[Fields.JOURNAL] = record_dict.pop("Publication Title", "")
            elif record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK:
                record_dict[Fields.BOOKTITLE] = record_dict.pop("Book Series Title", "")
            elif record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.INBOOK:
                record_dict[Fields.CHAPTER] = record_dict.pop("Item Title", "")
                record_dict[Fields.TITLE] = record_dict.pop("Publication Title", "")
            record_dict[Fields.VOLUME] = record_dict.pop("Journal Volume", "")
            record_dict[Fields.NUMBER] = record_dict.pop("Journal Issue", "")
            record_dict[Fields.DOI] = record_dict.pop("Item DOI", "")
            record_dict[Fields.AUTHOR] = record_dict.pop("Authors", "")
            record_dict[Fields.YEAR] = record_dict.pop("Publication Year", "")
            record_dict[Fields.URL] = record_dict.pop("URL", "")
            record_dict.pop("Content Type", None)

            # Fix authors
            # pylint: disable=colrev-missed-constant-usage
            if Fields.AUTHOR in record_dict:
                # a-bd-z: do not match McDonald
                record_dict[Fields.AUTHOR] = re.sub(
                    r"([a-bd-z]{1})([A-Z]{1})",
                    r"\g<1> and \g<2>",
                    record_dict["author"],
                )

            for key in list(record_dict.keys()):
                value = record_dict[key]
                record_dict[key] = str(value)
                if value == "" or pd.isna(value):
                    del record_dict[key]

        records = colrev.loader.load_utils.load(
            filename=filename,
            unique_id_field="Item DOI",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
            format_names=True,
        )
        return records

    def api_ui(self) -> None:
        """User API key insertion"""

        api_key = self.get_api_key()

        if not api_key:
            print("\n An API key is required for search \n\n")
            self._api_key_ui()
            return

        print("Your API key is available\n")

        change_api_key = [
            inquirer.List(
                name="change_api_key",
                message="Do you want to change your saved API key?",
                choices=["no", "yes"],
            ),
        ]

        answers = inquirer.prompt(change_api_key)

        if answers["change_api_key"] == "no":
            return

    def get_api_key(self) -> str:
        """Get API key from settings"""
        api_key = os.getenv("SPRINGER_API_KEY")
        if api_key:
            return api_key
        return ""

    def _is_springer_link_api_key(self, previous: dict, answer: str) -> bool:
        """Validate SpringerLink API key format"""
        api_key_pattern = re.compile(r"[a-z0-9]{32}")
        if not api_key_pattern.fullmatch(answer):
            raise inquirer.errors.ValidationError(
                "", reason="Invalid SpringerLink API key format."
            )

        full_url = self._build_api_search_url(
            query="doi:10.1007/978-3-319-07410-8_4", api_key=answer
        )
        try:
            self.api.validate_api_key(full_url, timeout=10)
        except springer_link_api.SpringerLinkAPIError as exc:
            raise inquirer.errors.ValidationError(
                "", reason="Error: Invalid API key."
            ) from exc
        print(
            f"\n{Colors.GREEN}Successfully authenticated with Springer Link API{Colors.END}"
        )
        return True

    def _is_year(self, previous: dict, answer: str) -> bool:
        """Validate year format"""
        year_pattern = re.compile(r"\d{4}")
        if not year_pattern.fullmatch(answer) and not answer == "":
            raise inquirer.errors.ValidationError("", reason="Invalid year format.")
        return True

    def _api_key_ui(self) -> None:
        """User Interface to enter API key"""

        questions = [
            inquirer.Text(
                "springer_api_key",
                message="Enter your Springer Link API key",
                validate=self._is_springer_link_api_key,
            ),
        ]
        answers = inquirer.prompt(questions)
        input_key = answers["springer_api_key"]
        os.environ["SPRINGER_API_KEY"] = input_key

    @classmethod
    def _load_bib(cls, *, filename: Path, logger: logging.Logger) -> dict:
        """Load bib file."""
        records = colrev.loader.load_utils.load(
            filename=filename,
            logger=logger,
            unique_id_field="ID",
            format_names=True,
        )
        return records

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".csv":
            return self._load_csv(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        if self.search_source.search_results_path.suffix == ".bib":
            return self._load_bib(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Springer Link"""

        return record
