#! /usr/bin/env python
"""SearchSource: IEEEXplore"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

import pandas as pd
from pydantic import Field

import colrev.env.environment_manager
import colrev.ops.prep
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.packages.ieee.src.ieee_api
import colrev.record.record
import colrev.record.record_prep
import colrev.search_file
import colrev.utils
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class IEEEXploreSearchSource(base_classes.SearchSourcePackageBaseClass):
    """IEEEXplore"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    flag = True

    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "ID"
    search_types = [SearchType.API, SearchType.DB]
    endpoint = "colrev.ieee"

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.oni

    db_url = "https://ieeexplore.ieee.org/Xplore/home.jsp"
    SETTINGS = {
        "api_key": "packages.search_source.colrev.ieee.api_key",
    }

    def __init__(
        self,
        *,
        search_file: typing.Optional[colrev.search_file.ExtendedSearchFile] = None,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode

        self.environment_manager = colrev.env.environment_manager.EnvironmentManager()

        if search_file:
            self.search_source = search_file
        else:
            self.search_source = colrev.search_file.ExtendedSearchFile(
                version=self.CURRENT_SYNTAX_VERSION,
                platform=self.endpoint,
                search_results_path=Path("data/search/ieee.bib"),
                search_type=SearchType.OTHER,
                search_string="",
                comment="",
            )

    # For run_search, a Python SDK would be available:
    # https://developer.ieee.org/Python_Software_Development_Kit

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for IEEEXplore"""

        result = {"confidence": 0.1}

        if "Date Added To Xplore" in data:
            result["confidence"] = 0.9
            return result

        return result

    # pylint: disable=too-many-locals
    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        search_type = colrev.utils.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.API:
            if len(params_dict) == 0:
                search_source = create_api_source(platform=cls.endpoint, path=path)
                search_source.search_parameters = {"query": search_source.search_string}
                search_source.search_string = ""

            # pylint: disable=colrev-missed-constant-usage
            elif (
                "https://ieeexploreapi.ieee.org/api/v1/search/articles?"
                in params_dict["url"]
            ):
                query = (
                    params_dict["url"]
                    .replace(
                        "https://ieeexploreapi.ieee.org/api/v1/search/articles?", ""
                    )
                    .lstrip("&")
                )

                parameter_pairs = query.split("&")
                search_parameters = {}
                for parameter in parameter_pairs:
                    key, value = parameter.split("=")
                    search_parameters[key] = value

                last_value = list(search_parameters.values())[-1]

                filename = colrev.utils.get_unique_filename(
                    base_path=path,
                    file_path_string=f"ieee_{last_value}",
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
                raise NotImplementedError

        elif search_type == SearchType.DB:
            search_source = create_db_source(
                path=path,
                platform=cls.endpoint,
                params=params_dict,
                add_to_git=True,
                logger=logger,
            )
        else:
            raise NotImplementedError
        return search_source

    def search(self, rerun: bool) -> None:
        """Run a search of IEEEXplore"""

        if self.search_source.search_type == SearchType.API:
            ieee_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                source_identifier=self.source_identifier,
                search_source=self.search_source,
                update_only=(not rerun),
                logger=self.logger,
                verbose_mode=self.verbose_mode,
            )
            self._run_api_search(ieee_feed=ieee_feed, rerun=rerun)

        elif self.search_source.search_type == SearchType.DB:
            run_db_search(
                db_url=self.db_url,
                source=self.search_source,
                add_to_git=True,
            )

        else:
            raise NotImplementedError

    def _get_api_key(self) -> str:
        api_key = self.environment_manager.get_settings_by_key(self.SETTINGS["api_key"])
        if api_key is None or len(api_key) != 24:
            api_key = input("Please enter api key: ")
            self.environment_manager.update_registry(self.SETTINGS["api_key"], api_key)
        return api_key

    def _run_api_search(
        self, ieee_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        api_key = self._get_api_key()

        api = colrev.packages.ieee.src.ieee_api.XPLORE(
            parameters=self.search_source.search_parameters, api_key=api_key
        )
        while True:
            retrieved_records = api.get_records()
            if not retrieved_records:
                break

            for retrieved_record in retrieved_records:
                ieee_feed.add_update_record(retrieved_record)

            api.startRecord += api.resultSetMax

        ieee_feed.save()

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
        def entrytype_setter(record_dict: dict) -> None:
            if record_dict["TY"] == "JOUR":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            elif record_dict["TY"] == "CONF":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
            else:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

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
                ENTRYTYPES.INPROCEEDINGS: {
                    "PY": Fields.YEAR,
                    "AU": Fields.AUTHOR,
                    "TI": Fields.TITLE,
                    "T2": Fields.BOOKTITLE,
                    "DO": Fields.DOI,
                    "SN": Fields.ISSN,
                },
            }

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
            if Fields.KEYWORDS in record_dict and isinstance(
                record_dict[Fields.KEYWORDS], list
            ):
                record_dict[Fields.KEYWORDS] = ", ".join(record_dict[Fields.KEYWORDS])

            record_dict.pop("TY", None)
            record_dict.pop("Y2", None)
            record_dict.pop("DB", None)
            record_dict.pop("C1", None)
            record_dict.pop("T3", None)
            record_dict.pop("AD", None)
            record_dict.pop("CY", None)
            record_dict.pop("M3", None)
            record_dict.pop("EP", None)
            record_dict.pop("Y1", None)
            record_dict.pop("Y2", None)
            record_dict.pop("JA", None)
            record_dict.pop("JO", None)
            record_dict.pop("VO", None)
            record_dict.pop("VL", None)
            record_dict.pop("IS", None)
            record_dict.pop("ER", None)

            for key, value in record_dict.items():
                record_dict[key] = str(value)

        records = colrev.loader.load_utils.load(
            filename=filename,
            unique_id_field="INCREMENTAL",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
            format_names=True,
        )

        return records

    @classmethod
    def ensure_append_only(cls, filename: Path) -> bool:
        """Ensure that the SearchSource file is append-only"""
        return filename.suffix in [".ris"]

    @classmethod
    def _load_csv(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            if record_dict["Category"] == "Magazine":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            elif record_dict["Category"] == "Conference Publication":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
            else:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

        def field_mapper(record_dict: dict) -> None:
            record_dict[Fields.TITLE] = record_dict.pop("Title", "")
            record_dict[Fields.AUTHOR] = record_dict.pop("Authors", "")
            record_dict[Fields.ABSTRACT] = record_dict.pop("Abstract", "")
            record_dict[Fields.DOI] = record_dict.pop("DOI", "")

            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
                record_dict[Fields.JOURNAL] = record_dict.pop("Publication", "")
            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
                record_dict[Fields.BOOKTITLE] = record_dict.pop("Publication", "")

            record_dict.pop("Category", None)
            record_dict.pop("Affiliations", None)

            for key in list(record_dict.keys()):
                value = record_dict[key]
                record_dict[key] = str(value)
                if value == "" or pd.isna(value):
                    del record_dict[key]

        records = colrev.loader.load_utils.load(
            filename=filename,
            unique_id_field="DOI",
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

        if self.search_source.search_results_path.suffix == ".csv":
            return self._load_csv(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for IEEEXplore"""

        if Fields.AUTHOR in record.data:
            record.data[Fields.AUTHOR] = (
                colrev.record.record_prep.PrepRecord.format_author_field(
                    record.data[Fields.AUTHOR]
                )
            )
        return record
