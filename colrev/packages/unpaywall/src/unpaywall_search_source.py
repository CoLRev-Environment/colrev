#! /usr/bin/env python
"""SearchSource: Unpaywall"""
from __future__ import annotations
import search_query

import logging
import typing
from pathlib import Path
from typing import Optional

from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.unpaywall.src.api import UnpaywallAPI

# pylint: disable=unused-argument


class UnpaywallSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Unpaywall Search Source"""

    source_identifier = "doi"
    search_types = [SearchType.API]
    endpoint = "colrev.unpaywall"

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.oni
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/unpaywall/README.md"
    )

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
        logger: Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode
        self.review_manager = source_operation.review_manager
        if settings:
            # Unpaywall as a search_source
            self.search_source = settings
        else:
            self.search_source = search_query.SearchFile(
                platform=self.endpoint,
                filepath=Path("data/search/unpaywall.bib"),
                search_type=SearchType.API,
                search_string={},
                comment="",
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Unpaywall"""
        result = {"confidence": 0.0}
        return result

    @classmethod
    def add_endpoint(
        cls, operation: colrev.ops.search.Search, params: str
    ) -> search_query.SearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        if len(params_dict) == 0:
            search_source = operation.create_api_source(platform=cls.endpoint)

        # pylint: disable=colrev-missed-constant-usage
        elif "https://api.unpaywall.org/v2/search" in params_dict["url"]:
            query = (
                params_dict["url"]
                .replace("https://api.unpaywall.org/v2/search?", "")
                .replace("https://api.unpaywall.org/v2/search/?", "")
                .lstrip("&")
            )

            parameter_pairs = query.split("&")
            search_parameters = {}
            for parameter in parameter_pairs:
                key, value = parameter.split("=")
                search_parameters[key] = value

            filename = operation.get_unique_filename(file_path_string="unpaywall")

            search_parameters["query"] = (
                UnpaywallAPI.decode_html_url_encoding_to_string(
                    query=search_parameters["query"]
                )
            )

            search_source = search_query.SearchFile(
                platform=cls.endpoint,
                filepath=filename,
                search_type=SearchType.API,
                search_string=search_parameters,
                comment="",
            )
        else:
            raise colrev_exceptions.PackageParameterError(
                f"Cannot add UNPAYWALL endpoint with query {params}"
            )

        operation.add_source_and_search(search_source)
        return search_source

    def _run_api_search(
        self, *, unpaywall_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:

        api = UnpaywallAPI(self.search_source.search_string)
        for record in api.get_query_records():
            unpaywall_feed.add_update_record(record)

        unpaywall_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of Unpaywall"""

        unpaywall_feed = self.search_source.get_api_feed(
            source_identifier=self.source_identifier,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        if self.search_source.search_type == SearchType.API:
            self._run_api_search(unpaywall_feed=unpaywall_feed, rerun=rerun)
        else:
            raise NotImplementedError

    @classmethod
    def load(cls, *, filename: Path, logger: logging.Logger) -> dict:
        """Load the records from the SearchSource file"""

        if filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=filename,
                logger=logger,
            )
            return records

        raise NotImplementedError

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    def prepare(
        self, record: colrev.record.record.Record, source: search_query.SearchFile
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Unpaywall"""
        return record