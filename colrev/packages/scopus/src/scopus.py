#! /usr/bin/env python
"""SearchSource: Scopus"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.loader.bib
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.record.record_prep
import colrev.utils
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search
from colrev.packages.scopus.src import scopus_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class ScopusSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Scopus"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.scopus"
    source_identifier = "scopus.eid"
    search_types = [SearchType.DB, SearchType.API]
    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "https://www.scopus.com/search/form.uri?display=advanced"

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.search_source = search_file
        self.verbose_mode = verbose_mode
        self.api = scopus_api.ScopusAPI(logger=self.logger)

    # ------------------------
    # API search + integration
    # ------------------------
    def _simple_api_search(self, query: str, rerun: bool) -> None:

        if not self.api.has_api_key():
            self.logger.info(
                'No API key found. Set API key using: export SCOPUS_API_KEY="XXXXX"'
            )
            return

        scopus_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        try:
            for record in self.api.iter_records(query=query):
                scopus_feed.add_update_record(retrieved_record=record)

        except ValueError as exc:
            self.logger.info("API search error: %s", str(exc))

        scopus_feed.save()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0.0}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
        elif "www.scopus.com" in data:
            if data.count("www.scopus.com") >= data.count("\n@"):
                result["confidence"] = 1.0
        return result

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        # params_dict = {params.split("=")[0]: params.split("=")[1]}

        # search_source = create_db_source(
        #     path=path,
        #     platform=cls.endpoint,
        #     params=params_dict,
        #     add_to_git=True,
        #     logger=logger,
        # )

        params_dict: dict = {}
        search_type = colrev.utils.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.API:
            search_source = create_api_source(platform=cls.endpoint, path=path)
            search_source.search_parameters = {"query": search_source.search_string}
            search_source.search_string = ""

        elif search_type == SearchType.DB:
            search_source = create_db_source(
                path=path,
                platform=cls.endpoint,
                params=params_dict,
                add_to_git=True,
                logger=logger,
            )
        else:
            raise NotImplementedError(
                f"Search type {search_type} not implemented for {cls.endpoint}"
            )

        return search_source

    def search(self, rerun: bool) -> None:
        query = self.search_source.search_parameters.get("query", "")

        if not query:
            raise ValueError("No query provided. Use --query when adding source.")

        if self.search_source.search_type == SearchType.API:
            self.logger.info(f"Running Scopus API search with: {query}")
            self._simple_api_search(query, rerun)
            return

        if self.search_source.search_type == SearchType.DB:
            run_db_search(
                db_url=self.db_url,
                source=self.search_source,
                add_to_git=True,
            )
            return

        raise NotImplementedError

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        return record

    @classmethod
    def _load_bib(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            if "document_type" in record_dict:
                if record_dict["document_type"] == "Conference Paper":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
                elif record_dict["document_type"] == "Conference Review":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.PROCEEDINGS
                elif record_dict["document_type"] == "Article":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE

        def field_mapper(record_dict: dict) -> None:
            if record_dict[Fields.ENTRYTYPE] in [
                ENTRYTYPES.INPROCEEDINGS,
                ENTRYTYPES.PROCEEDINGS,
            ]:
                record_dict[Fields.BOOKTITLE] = record_dict.pop(Fields.JOURNAL, None)

            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK:
                if (
                    Fields.JOURNAL in record_dict
                    and Fields.BOOKTITLE not in record_dict
                ):
                    record_dict[Fields.BOOKTITLE] = record_dict.pop(Fields.TITLE, None)
                    record_dict[Fields.TITLE] = record_dict.pop(Fields.JOURNAL, None)

            if "art_number" in record_dict:
                record_dict[f"{cls.endpoint}.art_number"] = record_dict.pop(
                    "art_number"
                )
            if "note" in record_dict:
                record_dict[f"{cls.endpoint}.note"] = record_dict.pop("note")
            if "document_type" in record_dict:
                record_dict[f"{cls.endpoint}.document_type"] = record_dict.pop(
                    "document_type"
                )
            if "source" in record_dict:
                record_dict[f"{cls.endpoint}.source"] = record_dict.pop("source")

            if "Start_Page" in record_dict and "End_Page" in record_dict:
                if (
                    record_dict["Start_Page"] != "nan"
                    and record_dict["End_Page"] != "nan"
                ):
                    record_dict[Fields.PAGES] = (
                        record_dict["Start_Page"] + "--" + record_dict["End_Page"]
                    ).replace(".0", "")
                    del record_dict["Start_Page"]
                    del record_dict["End_Page"]

        colrev.loader.bib.run_fix_bib_file(filename, logger=logger)
        records = colrev.loader.load_utils.load(
            filename=filename,
            unique_id_field="ID",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
        )
        return records

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".bib":
            return self._load_bib(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        return record
