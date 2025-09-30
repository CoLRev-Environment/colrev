#!/usr/bin/env python3
"""Searchsource:OSF"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.loader.load_utils
import colrev.ops.prep
import colrev.ops.search
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.process.operation
import colrev.record.record
import colrev.record.record_prep
import colrev.search_file
import colrev.utils
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.packages.osf.src.osf_api import OSFApiQuery

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class OSFSearchSource(base_classes.SearchSourcePackageBaseClass):
    """OSF"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    source_identifier = Fields.ID
    search_types = [SearchType.API]
    endpoint = "colrev.osf"

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.oni

    db_url = "https://osf.io/"
    SETTINGS = {
        "api_key": "packages.search_source.colrev.osf.api_key",
    }

    def __init__(
        self,
        *,
        search_file: typing.Optional[colrev.search_file.ExtendedSearchFile] = None,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode

        if search_file:
            self.search_source = search_file
        else:
            self.search_source = colrev.search_file.ExtendedSearchFile(
                version=self.CURRENT_SYNTAX_VERSION,
                platform=self.endpoint,
                search_results_path=Path("data/search/osf.bib"),
                search_type=SearchType.API,
                search_string="",
                comment="",
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for OSF"""

        result = {"confidence": 0.1}

        return result

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a)"""

        params_dict: typing.Dict[str, str] = {}
        if params and isinstance(params, str) and params.startswith("http"):
            params_dict = {Fields.URL: params}

        # Select the search type based on the provided parameters
        search_type = colrev.utils.select_search_type(
            search_types=cls.search_types, params={"query": params_dict}
        )

        # Handle different search types
        if search_type == SearchType.API:
            # Check for params being empty and initialize if needed
            if len(params_dict) == 0:
                search_source = create_api_source(platform=cls.endpoint, path=path)
                # Search title per default (other fields may be supported later)
                search_source.search_parameters = {
                    "description": search_source.search_string
                }

                search_source.search_string = ""
            elif "https://api.osf.io/v2/nodes/?filter" in params_dict.get("url", ""):
                query = (
                    params_dict["url"]
                    .replace("https://api.osf.io/v2/nodes/?filter", "")
                    .lstrip("&")
                )

                parameter_pairs = query.split("&")
                search_parameters = {
                    key.lstrip("[").rstrip("]"): value
                    for key, value in (pair.split("=") for pair in parameter_pairs)
                }
                last_value = list(search_parameters.values())[-1]
                filename = colrev.utils.get_unique_filename(
                    base_path=path,
                    file_path_string=f"osf_{last_value}",
                )
                search_source = colrev.search_file.ExtendedSearchFile(
                    version=cls.CURRENT_SYNTAX_VERSION,
                    platform=cls.endpoint,
                    search_results_path=filename,
                    search_type=SearchType.API,
                    search_string="",
                    search_parameters={"query": search_parameters},
                    comment="",
                )
        else:
            raise NotImplementedError("Unsupported search type.")

        # Adding the source and performing the search
        return search_source

    def _get_api_key(self) -> str:
        env_man = colrev.env.environment_manager.EnvironmentManager()
        api_key = env_man.get_settings_by_key(self.SETTINGS["api_key"])
        if api_key is None or len(api_key) == 0:
            api_key = input("Please enter api key: ")
            env_man.update_registry(self.SETTINGS["api_key"], api_key)
        return api_key

    def search(self, rerun: bool) -> None:
        """Run a search of OSF"""
        osf_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )
        self._run_api_search(osf_feed=osf_feed, rerun=rerun)

    def _run_api_search(
        self, osf_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:

        api = OSFApiQuery(
            parameters=self.search_source.search_parameters,
            api_key=self._get_api_key(),
        )
        self.logger.info(f"Retrieve {api.overall()} records")

        while True:
            for record_dict in api.retrieve_records():
                record = colrev.record.record.Record(record_dict)
                osf_feed.add_update_record(record)

            if api.pages_completed():
                break

        osf_feed.save()

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
    ) -> colrev.record.record.Record:
        """Needs manual preparation"""

        return record

    def load(self) -> dict:
        """Load the records."""

        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
                unique_id_field="ID",
            )
            return records

        raise NotImplementedError
