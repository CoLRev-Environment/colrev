#! /usr/bin/env python
"""SearchSource: JSTOR"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class JSTORSearchSource(base_classes.SearchSourcePackageBaseClass):
    """JSTOR"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.jstor"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [SearchType.DB]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "http://www.jstor.org"

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
        """Source heuristic for JSTOR"""

        result = {"confidence": 0.1}

        if "www.jstor.org:" in data:
            if data.count("www.jstor.org") > data.count("\n@"):
                result["confidence"] = 1.0
        if data.startswith("Provider: JSTOR http://www.jstor.org"):
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
        """Run a search of JSTOR"""

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
    def _load_ris(cls, *, filename: Path, logger: logging.Logger) -> dict:

        def id_labeler(records: list) -> None:
            for record_dict in records:
                record_dict[Fields.ID] = record_dict["UR"].split("/")[-1]

        def entrytype_setter(record_dict: dict) -> None:
            if record_dict["TY"] == "JOUR":
                record_dict[Fields.ENTRYTYPE] = "article"
            elif record_dict["TY"] == "RPRT":
                record_dict[Fields.ENTRYTYPE] = "techreport"
            elif record_dict["TY"] == "CHAP":
                record_dict[Fields.ENTRYTYPE] = "inbook"
            else:
                record_dict[Fields.ENTRYTYPE] = "misc"

        def field_mapper(record_dict: dict) -> None:

            key_maps = {
                ENTRYTYPES.ARTICLE: {
                    "PY": Fields.YEAR,
                    "AU": Fields.AUTHOR,
                    "TI": Fields.TITLE,
                    "T2": Fields.JOURNAL,
                    "AB": Fields.ABSTRACT,
                    "VL": Fields.VOLUME,
                    "IS": Fields.NUMBER,
                    "DO": Fields.DOI,
                    "PB": Fields.PUBLISHER,
                    "UR": Fields.URL,
                    "SN": Fields.ISSN,
                },
                ENTRYTYPES.INBOOK: {
                    "PY": Fields.YEAR,
                    "AU": Fields.AUTHOR,
                    "TI": Fields.CHAPTER,
                    "T2": Fields.TITLE,
                    "DO": Fields.DOI,
                    "PB": Fields.PUBLISHER,
                    "UR": Fields.URL,
                    "AB": Fields.ABSTRACT,
                    "SN": Fields.ISBN,
                    "A2": Fields.EDITOR,
                },
                ENTRYTYPES.TECHREPORT: {
                    "PY": Fields.YEAR,
                    "AU": Fields.AUTHOR,
                    "TI": Fields.TITLE,
                    "UR": Fields.URL,
                    "PB": Fields.PUBLISHER,
                },
            }

            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
                if "T1" in record_dict and "TI" not in record_dict:
                    record_dict["TI"] = record_dict.pop("T1")

            key_map = key_maps[record_dict[Fields.ENTRYTYPE]]
            for ris_key in list(record_dict.keys()):
                if ris_key in key_map:
                    standard_key = key_map[ris_key]
                    record_dict[standard_key] = record_dict.pop(ris_key)

            if "SP" in record_dict and "EP" in record_dict:
                record_dict[Fields.PAGES] = (
                    f"{record_dict.pop('SP')}--{record_dict.pop('EP')}"
                )

            if Fields.AUTHOR in record_dict and isinstance(
                record_dict[Fields.AUTHOR], list
            ):
                record_dict[Fields.AUTHOR] = " and ".join(record_dict[Fields.AUTHOR])
            if Fields.EDITOR in record_dict and isinstance(
                record_dict[Fields.EDITOR], list
            ):
                record_dict[Fields.EDITOR] = " and ".join(record_dict[Fields.EDITOR])

            record_dict.pop("TY", None)
            record_dict.pop("Y2", None)
            record_dict.pop("DB", None)
            record_dict.pop("C1", None)
            record_dict.pop("T3", None)
            record_dict.pop("ER", None)

            for key, value in record_dict.items():
                record_dict[key] = str(value)

        records = colrev.loader.load_utils.load(
            filename=filename,
            id_labeler=id_labeler,
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
        )

        return records

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".ris":
            return self._load_ris(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for JSTOR"""

        return record
