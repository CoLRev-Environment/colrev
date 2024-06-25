#! /usr/bin/env python
"""SearchSource: GitHub"""
from __future__ import annotations

import re
import typing
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from github import Auth
from github import Github

import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.packages.github.src.utils as connector_utils
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
"""pip install PyGithub -> Must be installed before use, please note in the documentation! """
# Authentication is defined via github.Auth

rerun = False


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class GitHubSearchSource(JsonSchemaMixin):
    """GitHub API"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    search_types = [SearchType.API]
    endpoint = "colrev.github"
    source_identifier = Fields.URL

    heuristic_status = SearchSourceHeuristicStatus.todo
    short_name = "GitHubSearch"
    docs_link = (
        "https://colrev.readthedocs.io/en/latest/dev_docs/packages/package_interfaces.html#colrev.package_manager.interfaces.SearchSourceInterface"
        + "https://docs.github.com/en/rest?apiVersion=2022-11-28"
    )
    db_url = "https://github.com/"
    SETTINGS = {
        "api_key": "packages.search_source.colrev.github.api_key",
    }
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
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # GitHub as a search source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            # GitHub as a md-prep source
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
        if Fields.URL in record.data:
            pattern = r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$"
            match = re.match(pattern, record.data[Fields.URL].strip('"'))
            if match:  # Check whether record contains GitHub url

                # get API access
                token = self._get_api_key()
                auth = Auth.Token(token)
                g = Github(auth=auth)

                repo = g.get_repo(match.group(1) + "/" + match.group(2))
                new_record = connector_utils.repo_to_record(repo=repo)
                record.data.update(new_record.data)

        return record

    @classmethod
    def add_endpoint(
        cls, operation: colrev.process.operation.Operation, params: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""
        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    try:
                        key, value = item.split("=")
                        if key in ["title", "readme"]:
                            params_dict[key] = value
                        else:
                            raise colrev_exceptions.InvalidQueryException(
                                "GitHub search_parameters support title or readme field"
                            )
                    except ValueError:
                        cls.review_manager.logger("Invalid search_parameter format")
        if len(params_dict) == 0:
            search_source = operation.create_api_source(endpoint="colrev.github")
        else:
            if Fields.URL in params_dict:
                query = {
                    "query": (
                        params_dict[Fields.URL]
                        .replace("https://github.com/search?q=%2F", "")
                        .replace("https://github.com/search?q=", "")
                        .replace("&type=repositories", "")
                        .replace("+", " ")
                    )
                }
            else:
                query = params_dict

            filename = operation.get_unique_filename(file_path_string="github")
            search_source = colrev.settings.SearchSource(
                endpoint="colrev.github",
                filename=filename,
                search_type=SearchType.API,
                search_parameters=query,
                comment="",
            )

        operation.add_source_and_search(search_source)
        return search_source

    def _get_api_key(self) -> str:
        api_key = self.review_manager.environment_manager.get_settings_by_key(
            self.SETTINGS["api_key"]
        )
        if api_key is None or len(api_key) != 40:
            api_key = input("Please enter api access token: ")
            self.review_manager.environment_manager.update_registry(
                self.SETTINGS["api_key"], api_key
            )
        return api_key

    def search(self, rerun: bool = False) -> None:
        """Run a search on GitHub"""

        if self.search_source.search_type == SearchType.API:
            github_feed = self.search_source.get_api_feed(
                review_manager=self.review_manager,
                source_identifier=self.source_identifier,
                update_only=(not rerun),
            )

            if not self.search_source.search_parameters:
                raise ValueError(
                    "No search parameters defined for GitHub search source"
                )

            # Checking where to search
            if rerun == False:
                choice_int = choice()
            query = ""
            keywords_input = self.search_source.search_parameters.get("query", "")
            if choice_int == 1:
                query = f"{keywords_input} in:name"
            if choice_int == 2:
                query = f"{keywords_input} in:readme"
            if choice_int == 3:
                query = f"{keywords_input} in:name,readme"

            # Getting API key
            token = self._get_api_key()
            auth = Auth.Token(token)
            g = Github(auth=auth)

            # Searching on Github
            repositories = g.search_repositories(query=query)

            # Saving search results
            results = []
            for repo in repositories:

                repo_data = {
                    Fields.ENTRYTYPE: "software",
                    Fields.URL: repo.html_url,
                }
                repo_data = colrev.record.record.Record(data=repo_data)

                try:
                    repo_data = connector_utils.repo_to_record(repo=repo)
                except Exception:
                    print("Could not convert record: " + repo.html_url)

                results.append(repo_data)

            for record in results:
                github_feed.add_update_record(retrieved_record=record)
            github_feed.save()

            g.close()

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        if self.search_source.filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                logger=self.review_manager.logger,
                unique_id_field="url",
            )

            return records
        raise NotImplementedError

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for GitHub"""
        return record


def choice() -> int:
    while True:
        user_choice = input(
            "Where do you want to search in (1 = Only in Title, 2 = Only in Readme, 3 = Both): "
        )
        if user_choice in ["1", "2", "3"]:
            rerun == True
            return int(user_choice)
        else:
            print("Invalid choice. Please try again.")
