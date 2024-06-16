#! /usr/bin/env python
"""SearchSource: GitHub"""
from __future__ import annotations

import typing
import json
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.packages.github.src.utils as connector_utils

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
    search_types = [
        SearchType.API, 
        SearchType.MD
        ]
    
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
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            #GitHub as a search source
            self.search_source = from_dict(data_class=self.settings_class, data=settings)
        else:
            #GitHub as a md-prep source
            github_md_source_l = [
                s
                for s in source_operation.review_manager.settings.sources
                if s.filename == self._github_md_filename
            ]
            if github_md_source_l:
                self.search_source = github_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint=self.endpoint,
                    filename=self._github_md_filename,
                    search_type=SearchType.MD,
                    search_parameters={},
                    comment="",
                )
            self.github_lock = Lock()

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
        if params: # right now parameters of the form title=[search term];readme=[search term] are accepted
            for item in params.split(";"):
                try:
                    key, value = item.split("=")
                    if key == "title" or key == "readme":
                        params_dict[key] = value
                except:
                    pass
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

    def search(self, rerun: bool = False) -> None:
        """Run a search on GitHub"""
        # Überprüfen Sie, ob die Suchparameter definiert sind
        if not self.search_source.search_parameters:
            raise ValueError("No search parameters defined for GitHub search source")

        # Erstellen einer GitHub-Instanz ohne Authentifizierung
        g = Github()

        # Extrahieren der Suchparameter
        title_query = self.search_source.search_parameters.get('title', '')
        readme_query = self.search_source.search_parameters.get('readme', '')
        
        # Erstellen der Suchanfrage
        query = ""
        if title_query:
            query += f"{title_query} in:name"
        if readme_query:
            if query:
                query += " "
            query += f"{readme_query} in:readme"
        
        if not query:
           raise ValueError("No valid search parameters found. Please provide at least one search parameter.")

        # Durchführen der Suche auf GitHub
        repositories = g.search_repositories(query)
        
        # Speichern der Suchergebnisse in einer Datei
        results = []
        for repo in repositories:
            repo_data = {
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "html_url": repo.html_url,
                "created_at": repo.created_at.isoformat(),
                "updated_at": repo.updated_at.isoformat(),
                "pushed_at": repo.pushed_at.isoformat(),
                "stargazers_count": repo.stargazers_count,
                "language": repo.language,
            }
            results.append(repo_data)
        
        # Speichern der Ergebnisse in einer JSON-Datei
        with open(self._github_md_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        
        # Schließen der GitHub-Verbindung
        g.close()


    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        return 

    def prepare(self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for GitHub"""

#   If __name__ == "__main__":
# Instance = github()
# Instance.search()