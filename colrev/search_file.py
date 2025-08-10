#!/usr/bin/env python3
"""Extended SearchFile with search_results_path and derived search_history_path."""
from __future__ import annotations

import json
import typing
from pathlib import Path
from typing import Any
from typing import Optional

import search_query

import colrev.git_repo
from colrev.constants import SearchType


class ExtendedSearchFile(search_query.SearchFile):
    """Extended SearchFile with search_results_path and derived search_history_path."""

    def __init__(
        self,
        search_string: str,
        platform: str,
        search_results_path: Path,
        search_type: SearchType,
        path: typing.Optional[Path] = Path("data/search"),
        authors: Optional[list[dict]] = None,
        record_info: Optional[dict] = None,
        date: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:

        # Mandatory attribute
        self.search_results_path = Path(search_results_path)
        self.search_type = SearchType(search_type)

        assert not str(search_results_path).endswith(
            "_search_history.json"
        ), "search_results_path should not end with _search_history.json"

        # Derived attribute
        self.search_history_path = Path(path) / Path(
            Path(search_results_path).stem + "_search_history.json"
        )

        super().__init__(
            search_string=search_string,
            platform=platform,
            authors=authors,
            record_info=record_info,
            date=date,
            filepath=self.search_history_path,
            # TODO : remove this:
            # search_results_path=Path(search_results_path),
            **kwargs,
        )

    def to_dict(self) -> dict:
        """Extend parent to_dict with search_results_path and search_history_path."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "search_results_path": str(self.search_results_path),
                "search_history_path": str(self.search_history_path),
                "search_type": self.search_type.value,
            }
        )
        return base_dict

    def model_dump(self, **kwargs) -> dict:  # type: ignore
        """Dump the search file with search_results_path and search_history_path."""
        return {
            "platform": self.platform,
            "search_results_path": str(self.search_results_path),
            # "search_history_path": str(self.search_history_path),
            "search_string": self.search_string,
            "search_type": self.search_type.value,
            # TODO check:
            # **kwargs,
        }

    def setup_for_load(
        self,
        *,
        source_records_list: typing.List[typing.Dict],
        imported_origins: typing.List[str],
    ) -> None:
        """Set the SearchSource up for the load process (initialize statistics)"""
        # pylint: disable=attribute-defined-outside-init
        # Note : define outside init because the following
        # attributes are temporary. They should not be
        # saved to SETTINGS_FILE.

        self.to_import = len(source_records_list)
        self.imported_origins: typing.List[str] = imported_origins
        self.len_before = len(imported_origins)
        self.source_records_list: typing.List[typing.Dict] = source_records_list

    def get_origin_prefix(self) -> str:
        """Get the corresponding origin prefix"""
        assert not any(x in str(self.search_results_path.name) for x in [";", "/"])
        return str(self.search_results_path.name).lstrip("/")

    def is_md_source(self) -> bool:
        """Check whether the source is a metadata source (for preparation)"""

        return str(self.search_results_path.name).startswith("md_")

    def is_curated_source(self) -> bool:
        """Check whether the source is a curated source (for preparation)"""

        return self.get_origin_prefix() == "md_curated.bib"

    def save(
        self,
        filepath: Optional[str | Path] = None,
        git_repo: typing.Optional[colrev.git_repo.GitRepo] = None,
    ) -> None:
        """Save the search file to a JSON file."""
        path = Path(filepath) if filepath else self._filepath
        if path is None:
            raise ValueError("No filepath provided and no previous filepath stored.")
        with open(path, "w", encoding="utf-8") as f:
            mod_dict = self.to_dict()
            mod_dict.pop("search_history_path", None)
            json.dump(mod_dict, f, indent=4, ensure_ascii=False)
        if git_repo:
            git_repo.add_changes(path)


load_search_file = search_query.load_search_file
