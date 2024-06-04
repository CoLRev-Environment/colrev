from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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

"""pip install PyGithub muss davor geschehen?"""
from github import Github
# Authentication is defined via github.Auth
from github import Auth
# using an access token
auth = Auth.Token("access_token")

# First create a Github instance:
# Public Web Github
g = Github(auth=auth)
# Github Enterprise with custom hostname
g = Github(base_url="https://{hostname}/api/v3", auth=auth)
"""
# Then play with your Github objects:
for repo in g.get_user().get_repos():
    print(repo.name)

# To close connections after use
g.close()
"""


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class GitHubSearchSource(JsonSchemaMixin):
    """GitHub Search"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.github"
    search_types = [SearchType.API] #Nicht ganz sicher, vllt MD? (Siehe open_library.py)
    

    def add_endpoint(cls,operation: colrev.ops.search.Search,params: str,) -> None:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""
        search_source = operation.create_db_source(search_source_cls=cls,params={})
        operation.add_source_and_search(search_source)
        

    def search(self,  rerun: bool) -> None:

    def load(self, load_operation: colrev.ops.load.Load) -> dict:


    def prepare(self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
