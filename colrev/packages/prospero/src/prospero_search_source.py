#!/usr/bin/env python
"""SearchSource: PROSPERO
import colrev.search_file

A CoLRev SearchSource plugin to scrape and import records from PROSPERO.
"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.packages.prospero.src.prospero_api
import colrev.process
import colrev.search_file
import colrev.utils
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source


class ProsperoSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Prospero Search Source for retrieving protocol data"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.prospero"
    source_identifier = Fields.PROSPERO_ID

    search_types = [SearchType.API]
    heuristic_status = SearchSourceHeuristicStatus.supported
    ci_supported: bool = Field(default=True)
    db_url = "https://www.crd.york.ac.uk/prospero/"

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        """Initialize the ProsperoSearchSource plugin."""

        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode
        self.search_source = search_file
        self.search_word: typing.Optional[str] = None

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Adds Prospero as a search source endpoint based on user-provided parameters."""
        if len(params) == 0:
            search_source = create_api_source(platform=cls.endpoint, path=path)
            search_source.search_string[Fields.URL] = (
                cls.db_url + "search?" + search_source.search_string + "#searchadvanced"
            )
            search_source.version = cls.CURRENT_SYNTAX_VERSION
            return search_source

        filename = colrev.utils.get_unique_filename(
            base_path=path,
            file_path_string="prospero_results",
        )

        new_search_source = colrev.search_file.ExtendedSearchFile(
            version=cls.CURRENT_SYNTAX_VERSION,
            platform=cls.endpoint,
            search_results_path=filename,
            search_type=SearchType.API,
            search_string=params,
            comment="Search source for Prospero protocols",
        )
        return new_search_source

    # pylint: disable=unused-argument
    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Prospero."""

        result = {"confidence": 0.0}
        return result

    def _validate_source(self) -> None:
        """Minimal source validation."""
        if not self.search_source:
            raise colrev_exceptions.InvalidQueryException("No search_source available.")
        if self.search_source.search_type not in self.search_types:
            raise colrev_exceptions.InvalidQueryException(
                f"Prospero search_type must be one of {self.search_types}, "
                f"not {self.search_source.search_type}"
            )
        if self.logger:
            self.logger.debug(
                "Validate SearchFile %s", self.search_source.search_results_path
            )

    def get_search_word(self) -> str:
        """
        Get the search query from settings or prompt the user.
        If there's no 'query' in the search_parameters, we ask the user.
        """
        if self.search_word is not None:
            return self.search_word

        if "query" in (self.search_source.search_string or {}):
            self.search_word = self.search_source.search_string["query"]
            self.logger.debug(
                "Using query from search_parameters: %s", self.search_word
            )
        else:
            self.search_word = input("Enter your search query: ").strip()
            self.logger.debug("Using user-input query: %s", self.search_word)

        return self.search_word

    def run_api_search(
        self, *, prospero_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        """Add newly scraped records to the feed."""
        if rerun:
            self.logger.info("Performing a search of the full history (may take time)")

        search_word = self.get_search_word()
        self.logger.info("Prospero search with query: %s", search_word)

        prospero_api = colrev.packages.prospero.src.prospero_api.PROSPEROAPI(
            search_word, logger=self.logger
        )

        for record_dict in prospero_api.get_next_record():
            self.logger.info("retrieve record: %s", record_dict[Fields.URL])

            try:
                if not record_dict.get(Fields.AUTHOR, "") and not record_dict.get(
                    Fields.TITLE, ""
                ):
                    continue
                prep_record = colrev.record.record_prep.PrepRecord(record_dict)
                prospero_feed.add_update_record(prep_record)
            except colrev_exceptions.NotFeedIdentifiableException:
                continue

        prospero_feed.save()

    def search(self, rerun: bool) -> None:
        """Scrape Prospero using Selenium, save .bib file with results."""

        self._validate_source()

        prospero_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=False,
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        self.run_api_search(prospero_feed=prospero_feed, rerun=rerun)

    # pylint: disable=unused-argument
    def prep_link_md(
        self,
        prep_operation: typing.Any,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Empty method as requested."""
        return record

    @classmethod
    def _load_bib(cls, *, filename: Path, logger: logging.Logger) -> dict:
        """Helper to load from .bib file using CoLRev's load_utils."""
        return colrev.loader.load_utils.load(
            filename=filename,
            logger=logger,
            unique_id_field="ID",
        )

    # pylint: disable=unused-argument
    def load(self) -> dict:
        """
        The interface requires a load method.
        We only handle .bib files here,
        so we raise NotImplementedError for other formats.
        """
        if self.search_source.search_results_path.suffix == ".bib":
            return self._load_bib(
                filename=self.search_source.search_results_path, logger=self.logger
            )
        raise NotImplementedError(
            "Only .bib loading is implemented for ProsperoSearchSource."
        )

    # pylint: disable=unused-argument
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Map fields to standardized fields for CoLRev (matching interface signature)."""
        return record
