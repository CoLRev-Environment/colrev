#! /usr/bin/env python
"""SearchSource: ACM Digital Library"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.utils
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search

if typing.TYPE_CHECKING:
    import colrev.search_file

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class ACMDigitalLibrarySearchSource(base_classes.SearchSourcePackageBaseClass):
    """ACM digital Library"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.acm_digital_library"
    # Note : the ID contains the doi
    # "https://dl.acm.org/doi/{{ID}}"
    source_identifier = "doi"
    search_types = [SearchType.DB]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported
    db_url = "https://dl.acm.org/"

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.search_source = search_file

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ACM dDigital Library"""

        result = {"confidence": 0.0}
        # Simple heuristic:
        if "publisher = {Association for Computing Machinery}," in data:
            result["confidence"] = 0.7
            return result
        # We may also check whether the ID=doi=url
        return result

    @classmethod
    def add_endpoint(
        cls, params: str, path: Path, logger: typing.Optional[logging.Logger] = None
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}
        if params:
            for item in params.split(";"):
                key, value = item.split("=")
                params_dict[key] = value

        search_type = colrev.utils.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.DB:
            search_source = create_db_source(
                path=path,
                platform=cls.endpoint,
                params=params_dict,
                add_to_git=True,
                logger=logger,
            )
        else:
            raise NotImplementedError

        # operation.add_source_and_search(search_source)
        # search_source.save()
        return search_source

    def search(self, rerun: bool) -> None:
        """Run a search of ACM Digital Library"""

        if self.search_source.search_type == SearchType.DB:
            if self.search_source.search_results_path.suffix in [".bib"]:
                run_db_search(
                    db_url=self.db_url,
                    source=self.search_source,
                    add_to_git=True,
                )
                return

            raise NotImplementedError
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

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".bib":

            def field_mapper(record_dict: dict) -> None:
                record_dict.pop("url", None)
                record_dict.pop("publisher", None)
                record_dict.pop("numpages", None)
                record_dict.pop("month", None)

                if "issue_date" in record_dict:
                    record_dict[f"{self.endpoint}.issue_date"] = record_dict.pop(
                        "issue_date"
                    )
                if "location" in record_dict:
                    record_dict[Fields.ADDRESS] = record_dict.pop("location", None)
                if "articleno" in record_dict:
                    record_dict[f"{self.endpoint}.articleno"] = record_dict.pop(
                        "articleno"
                    )

            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                unique_id_field="ID",
                field_mapper=field_mapper,
                logger=self.logger,
            )

            return records

        raise NotImplementedError

    # pylint: disable=colrev-missed-constant-usage
    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for ACM Digital Library"""

        return record
