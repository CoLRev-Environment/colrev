#! /usr/bin/env python
"""SearchSource: Taylor and Francis"""
from __future__ import annotations

import logging
import re
import typing
from pathlib import Path

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


class TaylorAndFrancisSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Taylor and Francis"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    db_url = "https://www.tandfonline.com/"
    endpoint = "colrev.taylor_and_francis"
    source_identifier = "{{doi}}"
    search_types = [SearchType.DB]
    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

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
        """Source heuristic for Taylor and Francis"""

        result = {"confidence": 0.0}

        if data.count("\n@") > 1:
            if data.count("eprint = { \n    \n    ") >= data.count("\n@"):
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
        """Run a search of TaylorAndFrancis"""

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
            if "note" in record_dict:
                record_dict[f"{cls.endpoint}.note"] = record_dict.pop("note")
            if "eprint" in record_dict:
                record_dict[f"{cls.endpoint}.eprint"] = record_dict.pop("eprint")

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
        """Source-specific preparation for Taylor and Francis"""

        # remove eprint and URL fields (they only have dois...)
        record.remove_field(key="colrev.taylor_and_francis.eprint")
        if "colrev.taylor_and_francis.note" in record.data and re.match(
            r"PMID: \d*", record.data["colrev.taylor_and_francis.note"]
        ):
            record.rename_field(
                key="colrev.taylor_and_francis.note", new_key=Fields.PUBMED_ID
            )
            record.data[Fields.PUBMED_ID] = record.data[Fields.PUBMED_ID][6:]

        return record
