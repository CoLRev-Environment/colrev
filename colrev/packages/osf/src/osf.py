"""Searchsource:OSF"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.environment_manager
import colrev.loader.load_utils
import colrev.ops.load
import colrev.ops.prep
import colrev.ops.search
import colrev.ops.search_api_feed
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.packages.osf.src.osf_api
import colrev.process.operation
import colrev.record.record
import colrev.record.record_prep
import colrev.review_manager
import colrev.settings
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.osf.src.osf_api import OSFApiQuery

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class OSFSearchSource(JsonSchemaMixin):
    """OSF"""

    flag = True
    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings

    source_identifier = Fields.ID
    search_types = [SearchType.API]
    endpoint = "colrev.osf"

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.oni
    short_name = "OSF SearchSource"
    db_url = "https://osf.io/"
    SETTINGS = {
        "api_key": "packages.osf.src.api_key",
    }

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager

        if settings:
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint=self.endpoint,
                filename=Path("data/search/osf.bib"),
                search_type=SearchType.API,
                search_parameters={},
                comment="",
            )
            self.source_operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for OSF"""

        result = {"confidence": 0.1}

        if "Date Added To OSF" in data:
            result["confidence"] = 0.9
            return result

        return result

    @classmethod
    def add_endpoint(
        cls, operation: colrev.ops.search.Search, params: dict = None
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a)"""

        params_dict = {}
        if params:
            if isinstance(params, str) and params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                # Handling the case where params might not be a string or None
                try:
                    for item in params.split(";"):
                        key, value = item.split("=")
                        params_dict[key] = value
                except AttributeError:
                    # handle the error appropriately if params is not a valid string
                    print("Invalid parameters provided.")
                    return None

        # Select the search type based on the provided parameters
        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        # Handle different search types
        if search_type == SearchType.API:
            # Check for params being empty and initialize if needed
            if len(params_dict) == 0:
                search_source = operation.create_api_source(endpoint=cls.endpoint)
                # Search title per default (other fields may be supported later)
                search_source.search_parameters["query"] = {
                    "title": search_source.search_parameters["query"]
                }
            elif "https://api.osf.io/v2/nodes/?filter" in params_dict.get("url", ""):
                query = (
                    params_dict["url"]
                    .replace("https://api.osf.io/v2/nodes/?filter", "")
                    .lstrip("&")
                )
                parameter_pairs = query.split("&")
                search_parameters = {
                    key: value
                    for key, value in (pair.split("=") for pair in parameter_pairs)
                }
                last_value = list(search_parameters.values())[-1]
                filename = operation.get_unique_filename(
                    file_path_string=f"osf_{last_value}"
                )
                search_source = colrev.settings.SearchSource(
                    endpoint=cls.endpoint,
                    filename=filename,
                    search_type=SearchType.API,
                    search_parameters=search_parameters,
                    comment="",
                )
        else:
            raise NotImplementedError("Unsupported search type.")

        # Adding the source and performing the search
        operation.add_source_and_search(search_source)
        return search_source

    def _get_api_key(self) -> str:
        api_key = self.review_manager.environment_manager.get_settings_by_key(
            self.SETTINGS["api_key"]
        )
        if api_key is None or len(api_key) == 0:
            api_key = input("Please enter api key: ")
            self.review_manager.environment_manager.update_registry(
                self.SETTINGS["api_key"], api_key
            )
        return api_key

    def search(self, rerun: bool) -> None:
        """Run a search of OSF"""
        osf_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )
        self._run_api_search(osf_feed=osf_feed, rerun=rerun)

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 60,
    ) -> colrev.record.record.Record:
        """Not implemented"""

        return record

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        source: colrev.settings.SearchSource,
    ) -> colrev.record.record.Record:
        """Needs manual preparation"""

        return record

    def run_api_query(self) -> colrev.packages.osf.src.osf_api.OSFApiQuery:
        api_key = self._get_api_key()
        query = colrev.packages.osf.src.osf_api.OSFApiQuery(api_key=api_key)
        query = OSFApiQuery(api_key)
        query.dataType("json")
        query.dataFormat("object")

        parameter_methods = {}
        parameter_methods["[title]"] = query.title
        parameter_methods["[id]"] = query.id
        parameter_methods["[year]"] = query.year
        parameter_methods["[description]"] = query.description
        parameter_methods["[tags]"] = query.tags
        parameter_methods["[date_created]"] = query.date_created

        parameters = self.search_source.search_parameters
        for key, value in parameters.items():
            if key in parameter_methods:
                method = parameter_methods[key]
                method(value)

        return query

    def _run_api_search(
        self, osf_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        query = self.run_api_query()
        query.startRecord = 1
        response = query.callAPI()
        links = response["links"]
        next = links["next"]

        self.review_manager.logger.info(
            f"Retrieve {response['links']['meta']['total']} records"
        )

        while "data" in response:
            articles = response["data"]

            for id in articles:

                record_dict = self._create_record_dict(id)
                record = colrev.record.record.Record(record_dict)
                osf_feed.add_update_record(record)

            if next == None:
                break

            query.page += 1
            query.startRecord += 10
            response = query.callAPI()
            links = response["links"]
            next = links["next"]

        osf_feed.save()

    def _create_record_dict(self, item: dict) -> dict:
        attributes = item["attributes"]
        year = attributes["date_created"]
        url = item["links"]
        relationships = item["relationships"]
        contributors = relationships["contributors"]
        links = contributors["links"]
        related = links["related"]
        record_dict = {
            Fields.ID: item["id"],
            Fields.ENTRYTYPE: "misc",
            Fields.AUTHOR: related["href"],
            Fields.TITLE: attributes["title"],
            Fields.ABSTRACT: attributes["description"],
            Fields.KEYWORDS: ", ".join(attributes["tags"]),
            Fields.YEAR: year[:4],
            Fields.URL: url["self"],
        }
        # Drop empty fields
        record_dict = {k: v for k, v in record_dict.items() if v}
        return record_dict

    def load(self, load_operation: colrev.ops.load.Load) -> dict:

        if self.search_source.filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )
            return records

        raise NotImplementedError
