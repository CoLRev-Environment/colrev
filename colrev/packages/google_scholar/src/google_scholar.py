#! /usr/bin/env python
"""SearchSource: GoogleScholar."""

from __future__ import annotations

import logging
import typing
from collections.abc import Callable
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


class GoogleScholarSearchSource(base_classes.SearchSourcePackageBaseClass):
    """GoogleScholar."""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.google_scholar"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [SearchType.DB]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "https://scholar.google.de/"

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        """Initialize the instance."""
        self.logger = logger or logging.getLogger(__name__)
        self.search_source = search_file

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for GoogleScholar."""
        result = {"confidence": 0.0}
        if data.count("https://scholar.google.com/scholar?q=relat") > 0.9 * data.count(
            "\n@"
        ):
            result["confidence"] = 1.0
            return result

        if data.count("{pop0") > 0.9 * data.count("\n@"):
            result["confidence"] = 1.0
            return result

        if (
            data.count("https://scholar.google.com/scholar?q=relat")
            == data.count('"uid": "GS:')
            and data.count('"uid": "GS:') > 0
        ):
            result["confidence"] = 1.0
            return result

        return result

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )."""
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
        """Run a search of GoogleScholar."""
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
        """Not implemented."""
        return record

    def _map_prefixed_fields(self, *, record_dict: dict, fields: list[str]) -> None:
        for field in fields:
            if field in record_dict:
                record_dict[f"{self.endpoint}.{field}"] = record_dict.pop(field)

    def _map_bib_fields(self, record_dict: dict) -> None:
        self._map_prefixed_fields(
            record_dict=record_dict, fields=["related", "note", "type"]
        )

    def _normalize_authors(self, record_dict: dict) -> None:
        if "authors" not in record_dict:
            return

        authors = record_dict.pop("authors")
        for i, author in enumerate(authors):
            names = author.split(" ")
            if len(names) > 1:
                first_name, last_name = names[0], " ".join(names[1:])
                authors[i] = f"{last_name}, {first_name}"
            else:
                authors[i] = names[0]

        record_dict[Fields.AUTHOR] = " and ".join(authors)

    def _map_json_fields(self, record_dict: dict) -> None:
        self._map_prefixed_fields(
            record_dict=record_dict,
            fields=[
                "related",
                "note",
                "type",
                "article_url",
                "cites_url",
                "related_url",
                "fulltext_url",
                "uid",
                "cites",
            ],
        )
        if "source" in record_dict:
            record_dict[Fields.JOURNAL] = record_dict.pop("source")

        record_dict.pop("volume", None)
        record_dict.pop("issue", None)
        record_dict.pop("startpage", None)
        record_dict.pop("endpage", None)
        record_dict.pop("ecc", None)
        record_dict.pop("use", None)
        record_dict.pop("rank", None)

        self._normalize_authors(record_dict)

        for key, value in record_dict.items():
            record_dict[key] = str(value)

    @staticmethod
    def _set_json_entrytype(record_dict: dict) -> None:
        record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

    def _load_records(
        self,
        *,
        field_mapper: Callable[[dict], None],
        entrytype_setter: typing.Optional[Callable[[dict], None]] = None,
        unique_id_field: typing.Optional[str] = None,
    ) -> dict:
        load_kwargs: dict[str, typing.Any] = {}
        if entrytype_setter is not None:
            load_kwargs["entrytype_setter"] = entrytype_setter
        if unique_id_field is not None:
            load_kwargs["unique_id_field"] = unique_id_field

        return colrev.loader.load_utils.load(
            filename=self.search_source.search_results_path,
            field_mapper=field_mapper,
            logger=self.logger,
            **load_kwargs,
        )

    def load(self) -> dict:
        """Load the records from the SearchSource file."""
        if self.search_source.search_results_path.suffix == ".bib":
            return self._load_records(field_mapper=self._map_bib_fields)

        if self.search_source.search_results_path.suffix == ".json":
            return self._load_records(
                field_mapper=self._map_json_fields,
                entrytype_setter=self._set_json_entrytype,
                # Note: uid not always available.
                unique_id_field="INCREMENTAL",
            )

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for GoogleScholar."""
        if "cites: https://scholar.google.com/scholar?cites=" in record.data.get(
            "note", ""
        ):
            note = record.data["note"]
            source_field = record.get_field_provenance_source("note")
            record.rename_field(key="note", new_key=Fields.CITED_BY)
            record.update_field(
                key=Fields.CITED_BY,
                value=record.data[Fields.CITED_BY][
                    : record.data[Fields.CITED_BY].find(" cites: ")
                ],
                source="replace_link",
            )
            record.update_field(
                key="cited_by_link",
                value=note[note.find("cites: ") + 7 :],
                append_edit=False,
                source=source_field + "|extract-from-note",
            )
        if Fields.ABSTRACT in record.data:
            # Note: abstracts provided by GoogleScholar are very incomplete
            record.remove_field(key=Fields.ABSTRACT)

        return record
