#! /usr/bin/env python
"""SearchSource: EBSCOHost."""

from __future__ import annotations

import logging
import re
import typing
from pathlib import Path

from pydantic import Field
from search_query.parser import parse

import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search
from colrev.record.name_parser import parse_names_in_records

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class EbscoHostSearchSource(base_classes.SearchSourcePackageBaseClass):
    """EBSCOHost."""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.ebsco_host"
    # https://connect.ebsco.com/s/article/
    # What-is-the-Accession-Number-AN-in-EBSCOhost-records?language=en_US
    # Note : ID is the accession number.
    source_identifier = "{{ID}}"
    search_types = [SearchType.DB]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "https://search.ebscohost.com/"

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        """Initialize the instance."""
        self.logger = logger or logging.getLogger(__name__)
        self.search_source = search_file
        self.validate_source(self.search_source)

    @classmethod
    def validate_source(
        cls, search_source: colrev.search_file.ExtendedSearchFile
    ) -> None:
        """Validate the search source."""
        if search_source.search_type == SearchType.DB:
            print(f"Validating search string: {search_source.search_string}")
            parse(search_source.search_string, platform="ebsco")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for EBSCOHost."""
        result = {"confidence": 0.0}

        if data.count("@") >= 1:
            if "URL = {https://search.ebscohost.com/" in data:
                if re.match(r"@.*{\d{17}\,\n", data):
                    result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint."""
        params_dict = {}
        if params:
            params_dict = {params.split("=")[0]: params.split("=")[1]}
        search_source = create_db_source(
            path=path,
            platform=cls.endpoint,
            params=params_dict,
            add_to_git=True,
            logger=logger,
        )
        return search_source

    def search(self, rerun: bool) -> None:
        """Run a search of EbscoHost."""
        if self.search_source.search_type == SearchType.DB:
            run_db_search(
                db_url=self.db_url,
                source=self.search_source,
                add_to_git=True,
            )
        else:
            raise NotImplementedError

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented."""
        return record

    @classmethod
    def normalize(
        cls, records: list[dict], *, format: str, source_version: str | None
    ) -> dict[str, dict]:
        """Lowercase EBSCO fields and normalize personal names."""
        for record_dict in records:
            for key in list(record_dict):
                if key not in [Fields.ID, Fields.ENTRYTYPE]:
                    record_dict[key.lower()] = record_dict.pop(key)
        indexed_records = super().normalize(
            records, format=format, source_version=source_version
        )
        parse_names_in_records(indexed_records)
        return indexed_records

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for EBSCOHost."""
        record.format_if_mostly_upper(Fields.AUTHOR, case=Fields.TITLE)
        record.format_if_mostly_upper(Fields.TITLE, case=Fields.TITLE)

        if record.data.get(Fields.PAGES) == "N.PAG -- N.PAG":
            record.data[Fields.PAGES] = FieldValues.UNKNOWN
        return record
