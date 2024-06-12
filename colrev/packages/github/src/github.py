#! /usr/bin/env python
"""SearchSource: GitHub"""
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

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for GitHub"""

        result = {"confidence": 0.0}

        return result

    def __init__(
        self, *, source_operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """TODO: Retrieve masterdata from the SearchSource"""
        return record
    
    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.process.operation.Operation,
        params: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""
        params_dict = {}
        if params:
            for item in params.split(";"):
                key, value = item.split("=")
                params_dict[key] = value
        if len(params_dict) == 0:
            search_source = operation.create_api_source(endpoint="colrev.github")
        else:
            filename = operation.get_unique_filename(file_path_string="github")
            search_source = colrev.settings.SearchSource(
                endpoint="colrev.github",
                filename=filename,
                search_type=SearchType.API,
                search_parameters=params_dict,
                comment="",
            )

        operation.add_source_and_search(search_source)
        return search_source
    
    @staticmethod
    def repo_to_record(*, repo: Github.Repository.Repository) -> dict:
        """Convert a GitHub repository to a record dict"""
        record_dict = {}
        record_dict[Fields.ENTRYTYPE] = "misc"
        record_dict[Fields.TITLE] = repo.name
        """format contributors into str"""
        contributors = "";
        for contributor in repo.get_contributors():
            contributor_name = contributor.login
            if not contributor_name.endswith("[bot]"): #filter out bots
                contributors = contributors + contributor_name + ", "
        contributors = contributors[:-2]
        record_dict[Fields.AUTHOR] = contributors

        record_dict[Fields.DATE] = repo.created_at.strftime("%m/%d/%Y")
        record_dict[Fields.ABSTRACT] = repo.description
        record_dict[Fields.URL] = "https://github.com/" + repo.full_name
        record_dict[Fields.LANGUAGE] = repo.language

        return record_dict

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