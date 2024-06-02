"""Searchsource:OSF"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import colrev.ops.search
import colrev.process
import colrev.process.operation
import colrev.settings
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

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
