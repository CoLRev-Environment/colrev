#! /usr/bin/env python
"""SearchSource: Unpaywall"""
from __future__ import annotations

import typing
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
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class UnpaywallSearchSource(JsonSchemaMixin):
    """Unpaywall Search Source"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    # source_identifier
    search_types = [SearchType.API]
    endpoint = "colrev.unpaywall"

    ci_supported: bool = False
    heuristic_status = SearchSourceHeuristicStatus.oni
    # docs_link

    short_name = "Unpaywall"

    API_FIELDS = [
        "best_oa_location",
        "best_oa_location.evidence",
        "best_oa_location.host_type",
        "best_oa_location.is_best",
        "best_oa_location.license",
        "best_oa_location.oa_date",
        "best_oa_location.pmh_id",
        "best_oa_location.updated",
        "best_oa_location.url",
        "best_oa_location.url_for_landing_page",
        "best_oa_location.url_for_pdf",
        "best_oa_location.version",
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
        "oa_locations",
        "oa_locations_embargoed",
        "first_oa_location",
        "oa_status",
        "has_repository_copy",
        "published_date",
        "publisher",
        "title",
        "updated",
        "year",
        "z_authors",
    ]

    FIELD_MAPPING = {
        "best_oa_location.url_for_pdf": Fields.FULLTEXT,
        "journal_name": Fields.JOURNAL,
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

            # Example URL: https://api.unpaywall.org/v2/search?query=cell%20thermometry&is_oa=true&email=unpaywall_01@example.com
            parameter_pairs = query.split("&")
            search_parameters = {}
            for parameter in parameter_pairs:
                key, value = parameter.split("=")
                search_parameters[key] = value

            filename = operation.get_unique_filename(file_path_string="unpaywall")

            search_source = colrev.settings.SearchSource(
                endpoint=cls.endpoint,
                filename=filename,
                search_type=SearchType.API,
                search_parameters=search_parameters,
                comment="",
            )
        else:
            raise NotImplementedError

        operation.add_source_and_search(search_source)

    def _run_api_search(
        self, *, unpaywall_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        for record in self._get_query_records():
            unpaywall_feed.add_update_record(record)

        unpaywall_feed.save()

    def _get_query_records(self) -> typing.Iterator[colrev.record.record.Record]:
        """Get the records from a query"""
        full_url = self._build_search_url()
        response = requests.get(full_url, timeout=90)
        if response.status_code != 200:
            return
        with open("test.json", "wb") as file:
            file.write(response.content)
        data = response.json()

        if "response" not in data["results"]:
            raise colrev_exceptions.ServiceNotAvailableException(
                "Could not reach API. Status Code: " + response.status_code
            )

        for article in data["results"]["response"]:
            record = self._create_record(article)
            yield record

    def _create_record(self, article: dict) -> colrev.record.record.Record:
        record_dict = {Fields.ID: article["doi"]}

        for field in self.API_FIELDS:
            if article.get(field) is None:
                continue
            record_dict[field] = str(article.get(field))

        for api_field, rec_field in self.FIELD_MAPPING.items():
            if api_field not in record_dict:
                continue
            record_dict[rec_field] = record_dict.pop(api_field)

        self._update_special_case_fields(record_dict=record_dict, article=article)

        record = colrev.record.record.Record(record_dict)
        return record

    def _build_search_url(self) -> str:
        url = "https://https://api.unpaywall.org/v2/search?"
        params = self.search_source.search_parameters
        for key in params.keys():
            if key == "query":
                url += "query=" + str(params["query"])
            elif key == "is_oa":
                url += "is_oa=" + str(params["is_oa"])
            elif key == "email":
                url += "email=" + str(params["email"])
            elif key == "page":
                url += "page=" + str(params["page"])
        return url

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
