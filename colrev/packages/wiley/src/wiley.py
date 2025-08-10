#! /usr/bin/env python
"""SearchSource: Wiley"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class WileyOnlineLibrarySearchSource(base_classes.SearchSourcePackageBaseClass):
    """Wiley"""

    endpoint = "colrev.wiley"
    source_identifier = "url"
    search_types = [SearchType.DB]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "https://onlinelibrary.wiley.com/"

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
        """Source heuristic for Wiley"""

        result = {"confidence": 0.0}

        # Simple heuristic:
        if "eprint = {https://onlinelibrary.wiley.com/doi/pdf/" in data:
            result["confidence"] = 0.7
            return result

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {params.split("=")[0]: params.split("=")[1]}

        search_source = create_db_source(
            review_manager=operation.review_manager,
            search_source_cls=cls,
            params=params_dict,
            add_to_git=True,
        )
        operation.add_source_and_search(search_source)
        return search_source

    def search(self, rerun: bool) -> None:
        """Run a search of Wiley"""

        if self.search_source.search_type == SearchType.DB:
            run_db_search(
                search_source_cls=self.__class__,
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
    def load(cls, *, filename: Path, logger: logging.Logger) -> dict:
        """Load the records from the SearchSource file"""

        if filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=filename,
                logger=logger,
                unique_id_field="ID",
            )
            for record_dict in records.values():
                if "eprint" not in record_dict:
                    continue
                record_dict[Fields.FULLTEXT] = record_dict.pop("eprint")
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record.Record,
        source: colrev.search_file.ExtendedSearchFile,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Wiley"""

        if record.data.get(Fields.ENTRYTYPE, "") == "inbook":
            record.rename_field(key=Fields.TITLE, new_key=Fields.CHAPTER)
            record.rename_field(key=Fields.BOOKTITLE, new_key=Fields.TITLE)

        return record
