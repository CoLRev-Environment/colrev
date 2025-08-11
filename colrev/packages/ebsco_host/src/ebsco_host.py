#! /usr/bin/env python
"""SearchSource: EBSCOHost"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class EbscoHostSearchSource(base_classes.SearchSourcePackageBaseClass):
    """EBSCOHost"""

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
        source_operation: colrev.process.operation.Operation,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.search_source = search_file
        self.source_operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for EBSCOHost"""

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
        logger: Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint"""

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
        """Run a search of EbscoHost"""

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
        """Not implemented"""
        return record

    @classmethod
    def _load_bib(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def field_mapper(record_dict: dict) -> None:
            for key in list(record_dict.keys()):
                if key not in ["ID", "ENTRYTYPE"]:
                    record_dict[key.lower()] = record_dict.pop(key)

        records = colrev.loader.load_utils.load(
            filename=filename,
            logger=logger,
            unique_id_field="ID",
            field_mapper=field_mapper,
            format_names=True,
        )
        return records

    @classmethod
    def load(cls, *, filename: Path, logger: logging.Logger) -> dict:
        """Load the records from the SearchSource file"""

        if filename.suffix == ".bib":
            return cls._load_bib(filename=filename, logger=logger)

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for EBSCOHost"""

        record.format_if_mostly_upper(Fields.AUTHOR, case=Fields.TITLE)
        record.format_if_mostly_upper(Fields.TITLE, case=Fields.TITLE)

        if record.data.get(Fields.PAGES) == "N.PAG -- N.PAG":
            record.data[Fields.PAGES] = FieldValues.UNKNOWN
        return record
