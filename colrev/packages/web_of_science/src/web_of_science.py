#! /usr/bin/env python
"""SearchSource: Web of Science"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field
from search_query.parser import parse

import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class WebOfScienceSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Web of Science"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.web_of_science"
    source_identifier = (
        "https://www.webofscience.com/wos/woscc/full-record/" + "{{unique-id}}"
    )
    search_types = [SearchType.DB]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "http://webofscience.com/"

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.search_source = search_file
        self.validate_source(self.search_source)

    @classmethod
    def validate_source(
        cls, search_source: colrev.search_file.ExtendedSearchFile
    ) -> None:
        """Validate the search source"""

        if search_source.search_type == SearchType.DB:
            print(f"Validating search string: {search_source.search_string}")
            parse(search_source.search_string, platform="wos")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Web of Science"""

        result = {"confidence": 0.0}

        if data.count("UT WOS:") > 0.4 * data.count("TI "):
            result["confidence"] = 0.7
            return result

        if "Unique-ID = {WOS:" in data:
            result["confidence"] = 0.7
            return result
        if "UT_(Unique_WOS_ID) = {WOS:" in data:
            result["confidence"] = 0.7
            return result
        if "@article{ WOS:" in data or "@article{WOS:" in data:
            if data.count("{WOS:") > data.count("\n@"):
                result["confidence"] = 1.0
            elif data.count("{ WOS:") > data.count("\n@"):
                result["confidence"] = 1.0
            else:
                result["confidence"] = 0.7

            return result

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
        params_dict: dict = {}

        search_source = create_db_source(
            path=path,
            platform=cls.endpoint,
            params=params_dict,
            add_to_git=True,
            logger=logger,
        )
        return search_source

    def search(self, rerun: bool) -> None:
        """Run a search of WebOfScience"""

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
        """Not implemented"""
        return record

    @classmethod
    def _load_bib(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def field_mapper(record_dict: dict) -> None:
            for key in list(record_dict.keys()):
                if key not in ["ID", "ENTRYTYPE"]:
                    record_dict[key.lower()] = record_dict.pop(key)
            record_dict.pop("book-group-author", None)
            record_dict.pop("organization", None)
            record_dict.pop("researcherid-numbers", None)
            if "eissn" in record_dict:
                if Fields.ISSN not in record_dict:
                    record_dict[Fields.ISSN] = record_dict.pop("eissn", "")
                else:
                    record_dict[Fields.ISSN] += ";" + record_dict.pop("eissn", "")
            if "note" in record_dict:
                record_dict[f"{cls.endpoint}.note"] = record_dict.pop("note")
            if "earlyaccessdate" in record_dict:
                record_dict[f"{cls.endpoint}.earlyaccessdate"] = record_dict.pop(
                    "earlyaccessdate"
                )
            if "article-number" in record_dict:
                record_dict[f"{cls.endpoint}.article-number"] = record_dict.pop(
                    "article-number"
                )
            if "orcid-numbers" in record_dict:
                record_dict[f"{cls.endpoint}.orcid-numbers"] = record_dict.pop(
                    "orcid-numbers"
                )
            if "unique-id" in record_dict:
                record_dict[f"{cls.endpoint}.unique-id"] = record_dict.pop("unique-id")
            if "book-author" in record_dict:
                record_dict[f"{cls.endpoint}.book-author"] = record_dict.pop(
                    "book-author"
                )

        records = colrev.loader.load_utils.load(
            filename=filename,
            logger=logger,
            unique_id_field="ID",
            field_mapper=field_mapper,
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
        """Source-specific preparation for Web of Science"""

        # pylint: disable=colrev-missed-constant-usage
        record.format_if_mostly_upper(Fields.TITLE, case="sentence")
        record.format_if_mostly_upper(Fields.JOURNAL, case="title")
        record.format_if_mostly_upper(Fields.BOOKTITLE, case="title")
        record.format_if_mostly_upper(Fields.AUTHOR, case="title")

        # record.remove_field(key="colrev.web_of_science.researcherid-numbers")
        # record.remove_field(key="colrev.web_of_science.orcid-numbers")
        # record.remove_field(key="colrev.web_of_science.book-group-author")
        # record.remove_field(key="colrev.web_of_science.note")
        # record.remove_field(key="colrev.web_of_science.organization")
        # record.remove_field(key="colrev.web_of_science.eissn")
        # record.remove_field(key="colrev.web_of_science.earlyaccessdate")

        # record.remove_field(key="colrev.web_of_science.meeting")
        # record.remove_field(key="colrev.web_of_science.article-number")

        if record.data[Fields.AUTHOR] == "[Anonymous]":
            del record.data[Fields.AUTHOR]
            record.add_field_provenance(
                key=Fields.AUTHOR, source="web_of_scienc.prep", note="IGNORE:missing"
            )

        return record
