#! /usr/bin/env python
"""SearchSource: Unpaywall"""
from __future__ import annotations

import re
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
from colrev.env.environment_manager import EnvironmentManager
from colrev.packages.unpaywall.src import utils

# pylint: disable=unused-argument


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class UnpaywallSearchSource(JsonSchemaMixin):
    """Unpaywall Search Source"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    source_identifier = "doi"
    search_types = [SearchType.API]
    endpoint = "colrev.unpaywall"

    ci_supported: bool = False
    heuristic_status = SearchSourceHeuristicStatus.oni
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/unpaywall/README.md"
    )

    short_name = "Unpaywall"

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
        elif "https://api.unpaywall.org/v2/search" in params_dict["url"]:
            query = (
                params_dict["url"]
                .replace("https://api.unpaywall.org/v2/search?", "")
                .replace("https://api.unpaywall.org/v2/search/?", "")
                .lstrip("&")
            )

            parameter_pairs = query.split("&")
            search_parameters = {}
            for parameter in parameter_pairs:
                key, value = parameter.split("=")
                search_parameters[key] = value

            filename = operation.get_unique_filename(file_path_string="unpaywall")

            search_parameters["query"] = cls._decode_html_url_encoding_to_string(
                query=search_parameters["query"]
            )

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
            for x in new_results:
                if x not in all_results:
                    all_results.append(x)

            if len(new_results) < results_per_page:
                break

            page += 1

        for result in all_results:
            article = result["response"]
            record = utils.create_record(article)
            yield record

    def _build_search_url(self, page: int) -> str:
        url = "https://api.unpaywall.org/v2/search?"
        params = self.search_source.search_parameters
        query = self._encode_query_for_html_url(params["query"])
        is_oa = params.get("is_oa", "null")
        email_param = params.get("email", "")

        if email_param and page == 1:

            env_man = EnvironmentManager()
            path = utils.UNPAYWALL_EMAIL_PATH
            value_string = email_param
            print(f"Updating registry settings:\n{path} = {value_string}")
            env_man.update_registry(path, value_string)

        email = utils.get_email(self.review_manager)

        return f"{url}query={query}&is_oa={is_oa}&page={page}&email={email}"

    @classmethod
    def _decode_html_url_encoding_to_string(cls, query: str) -> str:
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
        for x in splited_query:
            if not is_in_quotes and x.startswith('"'):
                parts.append(x)
                is_in_quotes = True
            elif is_in_quotes and x.endswith('"'):
                parts.append(x)
                is_in_quotes = False
            elif is_in_quotes:
                parts.append(x)
            else:
                x = x.replace("OR", "%20OR%20")
                x = x.replace("NOT", "%20-")
                x = x.replace("AND", "%20")
                x = x.replace(" ", "%20")
                parts.append(x)
        joined_query = "%20".join(parts)
        joined_query = re.sub(r"(%20)+", "%20", joined_query).strip()
        joined_query = joined_query.replace("-%20", "-")
        return joined_query

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
        return record
