from __future__ import annotations

import typing
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

# search repositories by name
for repo in g.search_repositories("pythoncode tutorials"): oder "suchbegriff" + in:readme && in:name (name = Name des Repos)
    # print repository details
    print_repo(repo)
    

# To close connections after use
g.close()
"""


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class GitHubSearchSource(JsonSchemaMixin):
    """GitHub API"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.github"
    search_types = [SearchType.API]

    heuristic_status = SearchSourceHeuristicStatus.todo
    short_name = "GitHubSearch"
    docs_link = (
        "https://colrev.readthedocs.io/en/latest/dev_docs/packages/package_interfaces.html#colrev.package_manager.interfaces.SearchSourceInterface"
        + "https://docs.github.com/en/rest?apiVersion=2022-11-28"
    )
    db_url = "https://github.com/"
    _github_md_filename = Path("data/search/md_github.bib")

    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for GitHub"""

        result = {"confidence": 0.0}

        return result

    def __init__(
        self, 
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            """GitHub as a search_source"""
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            """TODO: GitHub as an md-prep source"""
            pass
        
    def add_endpoint(cls,operation: colrev.ops.search.Search,params: str,) -> None:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""
        search_source = operation.create_db_source(search_source_cls=cls,params={})
        operation.add_source_and_search(search_source)
    
    
    def search(self,  rerun: bool) -> None:
        """Run a search of GitHub"""

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        return 

    def prepare(self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for GitHub"""


#   If __name__ == "__main__":
# Instance = github()
# Instance.search()