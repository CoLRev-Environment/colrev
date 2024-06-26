"""Searchsource:OSF"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.loader.load_utils
import colrev.ops.load
import colrev.ops.prep
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.packages.ieee.src.ieee_api
import colrev.record.record
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.osf_searchsource.src.osf_api import OSFApiQuery

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class OSFSearchSource(JsonSchemaMixin):
    """OSF"""

    flag = True
    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings

    source_identifier = "ID"
    search_types = [SearchType.API]
    endpoint = "colrev.osf"

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.oni
    short_name = "OSF SearchSource"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/osf_searchsource/README.md"
    )
    db_url = "https://osf.io/"
    SETTINGS = {
        "api_key": "packages.search_source.colrev.osf.api_key",
    }

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review.manager = source_operation.review_manager

        if settings:
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint=self.endpoint,
                filename=Path("data/search/osf.bib"),
                search_type=SearchType.OTHER,
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
        cls, operation: colrev.ops.search.Search, params: dict
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.API:
            if len(params) == 0:
                search_source = operation.add_api_source(endpoint=cls.endpoint)

            # pylint: disable=colrev-missed-constant-usage
            if "https://api.test.osf.io/v2/search" in params["url"]:
                query = (
                    params["url"]
                    .replace("https://api.test.osf.io/v2/search", "")
                    .lstrip("&")
                )

                parameter_pairs = query.split("&")
                search_parameters = {}
                for parameter in parameter_pairs:
                    key, value = parameter.split("=")
                    search_parameters[key] = value

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

        elif search_type == SearchType.DB:
            search_source = operation.create_db_source(
                search_source_cls=cls,
                params=params_dict,
            )

        else:
            raise NotImplementedError

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

    def search(self) -> None:
        """Run a search of OSF"""
        response = self.run_api_query()
        for item in response.get("data", []):
            record_dict = self._create_record_dict(item)
            record = colrev.record.record.Record(record_dict)
            self.source_operation.add_update_record(record)
        self.source_operation.save_records()

    def run_api_query(self) -> dict:
        api_key = self.get_api_key()
        base_url = "https://api.osf.io/v2/search/"
        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        query = OSFApiQuery(api_key)
        query.dataType("json")
        query.dataFormat("object")
        query.maximumResults(50000)

        parameter_methods = {
            "id": query.id,
            "type": query.type,
            "title": query.title,
            "category": query.category,
            "year": query.year,
            "ia_url": query.ia_url,
            "description": query.description,
            "tags": query.tags,
            "date_created": query.date_created,
        }

        parameters = self.search_source.search_parameters
        for key, value in parameters.items():
            if key in parameter_methods:
                method = parameter_methods[key]
                method(value)

        response = query.callAPI()
        return response

    def _create_record_dict(self, item: dict) -> dict:
        attributes = item["attributes"]
        record_dict = {
            Fields.ID: item["id"],
            Fields.TYPE: item["type"],
            Fields.TITLE: attributes.get("title", ""),
            Fields.CATEGORY: attributes.get("category", ""),
            Fields.YEAR: attributes.get("date_created", "")[:4],
            Fields.URL: attributes.get("ia_url", ""),
            Fields.DESCRIPTION: attributes.get("description", ""),
            Fields.TAGS: attributes.get("tags", ""),
            Fields.DATE_CREATED: attributes.get("date_created", ""),
        }
        return record_dict

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        def json_field_mapper(record_dict: dict) -> None:
            """Maps the different entries of the JSON file to endpoints"""
            if "title" in record_dict:
                record_dict[f"{self.endpoint}.title"] = record_dict.pop("title")
            if "description" in record_dict:
                record_dict[f"{self.endpoint}.description"] = record_dict.pop(
                    "description"
                )
            if "category" in record_dict:
                record_dict[f"{self.endpoint}.category"] = record_dict.pop("category")
            if "type" in record_dict:
                record_dict[f"{self.endpoint}.type"] = record_dict.pop("type")
            if "tags" in record_dict:
                record_dict[f"{self.endpoint}.tags"] = record_dict.pop("tags")
            if "date_created" in record_dict:
                record_dict[f"{self.endpoint}.date_created"] = record_dict.pop(
                    "date_created"
                )
            if "year" in record_dict:
                record_dict[f"{self.endpoint}.year"] = record_dict.pop("year")

            if "id" in record_dict:
                record_dict[f"{self.endpoint}.id"] = record_dict.pop("id")

            record_dict.pop("date_modified", None)
            record_dict.pop("custom_citation", None)
            record_dict.pop("registration", None)
            record_dict.pop("preprint", None)
            record_dict.pop("fork", None)
            record_dict.pop("collection", None)

            for key, value in record_dict.items():
                record_dict[key] = str(value)

        def json_entrytype_setter(record_dict: dict) -> None:
            """Loads the JSON file into the imported_md file"""
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                entrytype_setter=json_entrytype_setter,
                field_mapper=json_field_mapper,
                # Note: uid not always available.
                unique_id_field="INCREMENTAL",
                logger=self.review_manager.logger,
            )
            return records

    raise NotImplementedError
