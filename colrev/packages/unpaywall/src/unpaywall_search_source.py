#! /usr/bin/env python
"""SearchSource: Unpaywall"""
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
from colrev.constants import SearchSourceHeuristicStatus, SearchType
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
from colrev.constants import Fields
import colrev.record.record

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.unpaywall.src import utils
import re 


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class UnpaywallSearchSource(JsonSchemaMixin):
    """Unpaywall Search Source"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    source_identifier = "ID"
    search_types = [SearchType.API]
    endpoint = "colrev.unpaywall"

    ci_supported: bool = False
    heuristic_status = SearchSourceHeuristicStatus.oni
    # docs_link

    short_name = "Unpaywall"


    """API_FIELDS = [
        "data_standard",
        "doi",
        "doi_url",
        "genre",
        "is_paratext",
        "is_oa",
        "journal_is_in_doaj",
        "journal_is_oa",
        "journal_issns",
        "journal_issn_l",
        "journal_name",
        "oa_status",
        "has_repository_copy",
        "published_date",
        "publisher",
        "title",
        "updated",
        "year",
        "z_authors",
    ]"""

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
        "monograph": ENTRYTYPES.THESIS,  # thesis nicht auf website
        "report-component": ENTRYTYPES.TECHREPORT,
        "peer-review": ENTRYTYPES.MISC,  #
        "book-track": ENTRYTYPES.INCOLLECTION,  #
        "book-part": ENTRYTYPES.INBOOK,
        "journal-volume": ENTRYTYPES.ARTICLE,
        "book-set": ENTRYTYPES.MISC,
        "reference-entry": ENTRYTYPES.MISC,
        "journal": ENTRYTYPES.ARTICLE,  #
        "component": ENTRYTYPES.MISC,
        "proceedings-series": ENTRYTYPES.PROCEEDINGS,  # oder Misc da serie
        "report-series": ENTRYTYPES.TECHREPORT,  # oder misc da series und nicht ein report
        "proceedings": ENTRYTYPES.PROCEEDINGS,
        "database": ENTRYTYPES.MISC,
        "standard": ENTRYTYPES.MISC,
        "reference-book": ENTRYTYPES.BOOK,
        "posted-content": ENTRYTYPES.MISC,
        "journal-issue": ENTRYTYPES.ARTICLE,  # Misc?
        "grant": ENTRYTYPES.MISC,
        "dataset": ENTRYTYPES.MISC,
        "book-series": ENTRYTYPES.BOOK,  # oder Misc, da Serie?
        "edited-book": ENTRYTYPES.BOOK,
    }

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # Unpaywall as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint=self.endpoint,
                filename=Path("data/search/unpaywall.bib"),
                search_type=SearchType.API,
                search_parameters={},
                comment="",
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Unpaywall"""
        # Not yet implemented
        result = {"confidence": 0.0}
        return result

    @classmethod
    def add_endpoint(cls, operation: colrev.ops.search.Search, params: str) -> None:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        if len(params_dict) == 0:
            search_source = operation.create_api_source(endpoint=cls.endpoint)

        # pylint: disable=colrev-missed-constant-usage
        elif "https://api.unpaywall.org/v2/search?" in params_dict["url"]:
            query = (
                params_dict["url"]
                .replace("https://api.unpaywall.org/v2/search?", "")
                .lstrip("&")
            )

            parameter_pairs = query.split("&")
            search_parameters = {}
            for parameter in parameter_pairs:
                key, value = parameter.split("=")
                search_parameters[key] = value

            filename = operation.get_unique_filename(file_path_string="unpaywall")

            search_parameters["query"] = cls._normalize_query(query=search_parameters["query"])
            search_parameters["query"] = cls._convert_html_url_encoding_from_html_to_string(query=search_parameters["query"])

            search_source = colrev.settings.SearchSource(
                endpoint=cls.endpoint,
                filename=filename,
                search_type=SearchType.API,
                search_parameters=search_parameters,
                comment="",
            )
        else:
            raise colrev_exceptions.PackageParameterError(
                f"Cannot add UNPAYWALL endpoint with query {params}"
            )

        operation.add_source_and_search(search_source)

    
    def _run_api_search(
        self, *, unpaywall_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        for record in self.get_query_records():
            unpaywall_feed.add_update_record(record)

        unpaywall_feed.save()

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
            all_results.extend(new_results)

            if len(new_results) < results_per_page:
                break

            page += 1
    
        with open(f"all_results.json", "wb") as file:
            file.write(response.content)

        for result in all_results:
            article = result["response"]
            record = self._create_record(article)
            yield record

    def _get_authors(self, article: dict) -> typing.List[str]:
        authors = []
        z_authors = article.get("z_authors", [])
        if z_authors:
            for author in z_authors:
                given_name = author.get("given", "")
                family_name = author.get("family", "")
                authors.append(f"{family_name}, {given_name}")
        return authors

    def _create_record(self, article: dict) -> colrev.record.record.Record:
        record_dict = {Fields.ID: article["doi"]}

        entrytype = self.ENTRYTYPE_MAPPING.get(
            article.get("genre", "other"), ENTRYTYPES.MISC
        )
        record_dict[Fields.ENTRYTYPE] = entrytype

        record_dict[Fields.AUTHOR] = " and ".join(self._get_authors(article))
        record_dict[Fields.TITLE] = article.get("title", "")
        record_dict[Fields.YExAR] = article.get("year", "")

        if entrytype == ENTRYTYPES.ARTICLE:
            record_dict[Fields.JOURNAL] = article.get("journal_name", "")
        elif entrytype == ENTRYTYPES.BOOK:
            record_dict[Fields.PUBLISHER] = article.get("publisher", "")
        elif entrytype == ENTRYTYPES.INPROCEEDINGS:
            record_dict[Fields.BOOKTITLE] = article.get("booktitle", "")
        elif entrytype == ENTRYTYPES.INBOOK:
            record_dict[Fields.BOOKTITLE] = article.get("booktitle", "")
            record_dict[Fields.PUBLISHER] = article.get("publisher", "")
        elif entrytype == ENTRYTYPES.CONFERENCE:
            record_dict[Fields.BOOKTITLE] = article.get("booktitle", "")
        elif entrytype == ENTRYTYPES.PHDTHESIS:
            record_dict[Fields.SCHOOL] = article.get("school", "")  # oder publisher?
        elif entrytype == ENTRYTYPES.TECHREPORT:
            record_dict[Fields.INSTITUTION] = article.get(
                "publisher", ""
            )  # habe hier als default publisher, richtig?

        record = colrev.record.record.Record(record_dict)

        return record

    def _build_search_url(self,page) -> str:
        url = "https://api.unpaywall.org/v2/search?"
        params = self.search_source.search_parameters
        query = self._convert_html_url_encoding_from_string_to_html(params["query"]) 
        is_oa = params.get("is_oa", "null")
        email = params.get("email", utils.get_email(self.review_manager))

        return f"{url}query={query}&is_oa={is_oa}&page={page}&email={email}"
    
    def _normalize_query(query: str) -> str:
        query = query.replace(" AND ", " ")
        return query
    
    def _convert_html_url_encoding_from_html_to_string(query: str) -> str: 
        query = query.replace("%20", " AND ")
        query = query.replace("%20OR%20", " OR ")
        query = query.replace("%20-", " NOT ")
        return query
    
    def _convert_html_url_encoding_from_string_to_html(self,query: str) -> str: 
        query = re.sub(r'\s+', ' ', query).strip() 
        splited_query = query.split(" ")
        query_parts = []
        for part in splited_query:
            if part == "AND" or part == "OR" or part == "NOT":
                continue
            part = part.lower()
            query_parts.append(part)	
        query = " ".join(query_parts)
        query = query.replace(" OR ", "%20OR%20")
        query = query.replace(" NOT ", "%20-")
        query = query.replace(" AND ", "%20")
        query = query.replace(" ", "%20")
        return query   
     
    def search(self, rerun: bool) -> None:
        """Run a search of Unpaywall"""

        unpaywall_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type == SearchType.API:
            self._run_api_search(unpaywall_feed=unpaywall_feed, rerun=rerun)
        else:
            raise NotImplementedError

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                logger=self.review_manager.logger,
            )
            return records

        raise NotImplementedError
  
    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Unpaywall"""
        """Not implemented"""
        return record
        
   

