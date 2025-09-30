#! /usr/bin/env python
"""SearchSource: Unpaywall"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.search_file
import colrev.utils
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.packages.unpaywall.src.api import UnpaywallAPI

# pylint: disable=unused-argument


class UnpaywallSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Unpaywall Search Source"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

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
        search_file: typing.Optional[colrev.search_file.ExtendedSearchFile] = None,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode

        if search_file:
            # Unpaywall as a search_source
            self.search_source = search_file
        else:
            self.search_source = colrev.search_file.ExtendedSearchFile(
                version=self.CURRENT_SYNTAX_VERSION,
                platform=self.endpoint,
                search_results_path=Path("data/search/unpaywall.bib"),
                search_type=SearchType.API,
                search_string="",
                comment="",
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Unpaywall"""
        result = {"confidence": 0.0}
        return result

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
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
            search_source = create_api_source(platform=cls.endpoint, path=path)
            search_source.search_parameters = {}
            search_source.search_parameters["query"] = search_source.search_string
            search_source.search_string = ""

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

            filename = colrev.utils.get_unique_filename(
                base_path=path,
                file_path_string="unpaywall",
            )

            search_parameters["query"] = (
                UnpaywallAPI.decode_html_url_encoding_to_string(
                    query=search_parameters["query"]
                )
            )

            search_source = colrev.search_file.ExtendedSearchFile(
                version=cls.CURRENT_SYNTAX_VERSION,
                platform=cls.endpoint,
                search_results_path=filename,
                search_type=SearchType.API,
                search_string="",
                search_parameters=search_parameters,
                comment="",
            )
        else:
            raise colrev_exceptions.PackageParameterError(
                f"Cannot add UNPAYWALL endpoint with query {params}"
            )
        return search_source

    def _run_api_search(
        self, *, unpaywall_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:

        api = UnpaywallAPI(self.search_source.search_parameters)
        for record in api.get_query_records():
            unpaywall_feed.add_update_record(record)

        unpaywall_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of Unpaywall"""

        unpaywall_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        if self.search_source.search_type == SearchType.API:
            self._run_api_search(unpaywall_feed=unpaywall_feed, rerun=rerun)
        else:
            raise NotImplementedError

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
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
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Unpaywall"""
        return record
