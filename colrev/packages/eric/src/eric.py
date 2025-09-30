#! /usr/bin/env python
"""SearchSource: ERIC"""
from __future__ import annotations

import logging
import typing
import urllib.parse
from pathlib import Path

from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.search_file
import colrev.utils
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search_api_feed import create_api_source
from colrev.ops.search_db import create_db_source
from colrev.ops.search_db import run_db_search
from colrev.packages.eric.src import eric_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class ERICSearchSource(base_classes.SearchSourcePackageBaseClass):
    """ERIC API"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "ID"
    search_types = [SearchType.API, SearchType.DB]
    endpoint = "colrev.eric"

    db_url = "https://eric.ed.gov/"

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.oni

    def __init__(
        self,
        *,
        search_file: typing.Optional[colrev.search_file.ExtendedSearchFile] = None,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode

        if search_file:
            # ERIC as a search_source
            self.search_source = search_file
        else:
            self.search_source = colrev.search_file.ExtendedSearchFile(
                version=self.CURRENT_SYNTAX_VERSION,
                platform=self.endpoint,
                search_results_path=Path("data/search/eric.bib"),
                search_type=SearchType.OTHER,
                search_string="",
                comment="",
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ERIC"""

        result = {"confidence": 0.1}

        if "OWN - ERIC" in data:
            # if data.count("OWN - ERIC") > data.count("\n\n"):
            result["confidence"] = 1.0

        # Note : no features in bib file for identification

        return result

    @classmethod
    def _search_split(cls, search: str) -> str:
        if " AND " in search:
            search_parts = search.split(" AND ")
            field_values = []
            for part in search_parts:
                field, value = part.split(":")
                field = field.strip()
                value = value.strip().strip("'")
                field_value = f"{field}%3A%22{urllib.parse.quote(value)}%22"
                field_values.append(field_value)
            return " AND ".join(field_values)

        field, value = search.split(":")
        field = field.strip()
        value = value.strip().strip("'")
        field_value = f"{field}%3A%22{urllib.parse.quote(value)}%22"
        return field_value

    # pylint: disable=too-many-locals
    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a)"""

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

        if search_type == SearchType.DB:
            search_source = create_db_source(
                path=path,
                platform=cls.endpoint,
                params=params_dict,
                add_to_git=True,
                logger=logger,
            )

        if search_type == SearchType.API:
            # pylint: disable=colrev-missed-constant-usage
            if params_dict and "https://api.ies.ed.gov/eric/?" in params_dict["url"]:
                url_parsed = urllib.parse.urlparse(params_dict["url"])
                new_query = urllib.parse.parse_qs(url_parsed.query)
                search = new_query.get("search", [""])[0]
                start = new_query.get("start", ["0"])[0]
                rows = new_query.get("rows", ["2000"])[0]
                if ":" in search:
                    search = ERICSearchSource._search_split(search)
                filename = colrev.utils.get_unique_filename(
                    base_path=path,
                    file_path_string=f"eric_{search}",
                )
                search_source = colrev.search_file.ExtendedSearchFile(
                    version=cls.CURRENT_SYNTAX_VERSION,
                    platform=cls.endpoint,
                    search_results_path=filename,
                    search_type=SearchType.API,
                    search_string="",
                    search_parameters={"query": search, "start": start, "rows": rows},
                    comment="",
                )
            else:
                search_source = create_api_source(platform=cls.endpoint, path=path)
                search_source.search_parameters = {"query": search_source.search_string}
                search_source.search_string = ""

        else:
            raise colrev_exceptions.PackageParameterError(
                f"Cannot add ERIC endpoint with query {params_dict}"
            )
        return search_source

    def _run_api_search(
        self, *, eric_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:

        api = eric_api.ERICAPI(params=self.search_source.search_parameters)
        for record in api.get_query_return():
            eric_feed.add_update_record(record)

        eric_feed.save()

    def search(self, rerun: bool) -> None:
        """Run a search of ERIC"""

        eric_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        if self.search_source.search_type == SearchType.API:
            self._run_api_search(eric_feed=eric_feed, rerun=rerun)
        elif self.search_source.search_type == SearchType.DB:
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
    def _load_nbib(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            if "Journal Articles" in record_dict["PT"]:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            else:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

        def field_mapper(record_dict: dict) -> None:

            key_maps = {
                ENTRYTYPES.ARTICLE: {
                    "TI": Fields.TITLE,
                    "AU": Fields.AUTHOR,
                    "DP": Fields.YEAR,
                    "JT": Fields.JOURNAL,
                    "VI": Fields.VOLUME,
                    "IP": Fields.NUMBER,
                    "PG": Fields.PAGES,
                    "AB": Fields.ABSTRACT,
                    "AID": Fields.DOI,
                    "ISSN": Fields.ISSN,
                    "OID": f"{cls.endpoint}.eric_id",
                    "OT": Fields.KEYWORDS,
                    "LA": Fields.LANGUAGE,
                    "PT": "type",
                    "LID": f"{cls.endpoint}.eric_url",
                }
            }

            key_map = key_maps[record_dict[Fields.ENTRYTYPE]]
            for ris_key in list(record_dict.keys()):
                if ris_key in key_map:
                    standard_key = key_map[ris_key]
                    record_dict[standard_key] = record_dict.pop(ris_key)

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

            record_dict.pop("type", None)
            record_dict.pop("OWN", None)
            record_dict.pop("SO", None)

            for key, value in record_dict.items():
                record_dict[key] = str(value)

        records = colrev.loader.load_utils.load(
            filename=filename,
            unique_id_field="OID",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
        )

        return records

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".nbib":
            return self._load_nbib(
                filename=self.search_source.search_results_path, logger=self.logger
            )

        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
            )
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for ERIC"""

        if Fields.ISSN in record.data:
            record.data[Fields.ISSN] = record.data[Fields.ISSN].lstrip("ISSN-")

        return record
