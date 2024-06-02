"""Searchsource:OSF"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from colrev.packages.osf_searchsource.src.osf_api import OSFApiQuery
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
    # SETTINGS = {
    #     "api_key": "packages.search_source.colrev.osf.api_key",
    # }

    def __init__(
            self,
            *, 
            source_operation: colrev.process.operation.Operation,
            settings: typing.Optional[dict] = None,) -> None:
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
    def heuristic(cls, filename:Path, data:str) -> dict:
        """Source heuristic for OSF"""

        result = {"confidence": 0.1}

        if "Date Added To OSF" in data:
            result["confidence"] = 0.9
            return result

        return result

    @classmethod
    def add_endpoint(
         cls,
         operation:colrev.ops.search.Search, 
         params: dict
    ) -> colrev.settings.SearchSource:
         """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

         search_type = operation.select_search_type(
              search_types=cls.search_types, params=params
         )

         if search_type == SearchType.API:
              if len(params) == 0:
                   add_source = operation.add_api_source(endpoint=cls.endpoint)
                   return add_source
              
              # pylint: disable=colrev-missed-constant-usage
              if (
                   "https://api.test.osf.io/v2/search"
                   in params["url"]
                ):
                query = (
                    params["url"]
                    .replace(
                        "https://api.test.osf.io/v2/search", ""
                    )
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

                add_source = colrev.settings.SearchSource(
                    endpoint=cls.endpoint,
                    filename=filename,
                    search_type=SearchType.API,
                    search_parameters=search_parameters,
                    comment="",
                )
                return add_source
              
              if search_type == SearchType.DB:
                  return operation.add_db_source(
                      search_source_cls=cls,
                      params=params,
                      )

                  raise NotImplementedError
    
    
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
        api_key = self.get_api_key()
        query = OSFApiQuery(api_key)
        query.dataType("json")
        query.dataFormat("object")
        query.maximumResults(50000)

        parameter_methods = {
            "id": query.id,
            "type": query.type,
            "author": query.author,
            "doi": query.doi,
            "publisher": query.publisher,
            "title": query.title,
            "links": query.links,
        }

        parameters = self.search_source.search_parameters
        for key, value in parameters.items():
            if key in parameter_methods:
                method = parameter_methods[key]
                method(value)

        response = query.callAPI()
        return response

    def _create_record_dict(self, item: dict) -> dict:
        record_dict = {
            Fields.ID: item["id"],
            Fields.TITLE: item["attributes"]["title"],
            Fields.ABSTRACT: item["attributes"]["description"],
            Fields.AUTHOR: ", ".join(contributor["embeds"]["users"]["data"]["attributes"]["full_name"] for contributor in item["embeds"]["contributors"]["data"]),
            Fields.YEAR: item["attributes"]["date_created"][:4],
            Fields.URL: item["links"]["html"],
        }
        return record_dict

    def _load_bib(self) -> dict:

        records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            logger=self.review_manager.logger,
            unique_id_field="ID",
        )
        for record_dict in records.values():
            record_dict.pop("type", None)

        return records

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        if self.search_source.filename.suffix == ".bib":
            return self._load_bib()
        raise NotImplementedError


    def prepare():
        #need the dict method to create the prepare method