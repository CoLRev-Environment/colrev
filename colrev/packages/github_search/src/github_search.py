from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class GitHubSearchSource(JsonSchemaMixin):

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.github_search"

    def add_endpoint(cls,operation: colrev.ops.search.Search,params: str,) -> None:
           """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        search_source = operation.create_db_source(search_source_cls=cls,params={})
        operation.add_source_and_search(search_source)

    def search(self,  rerun: bool) -> None:

    def load(self, load_operation: colrev.ops.load.Load) -> dict:


    def prepare(self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
