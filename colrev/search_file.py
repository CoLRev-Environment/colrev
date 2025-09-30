#!/usr/bin/env python3
"""Extended SearchFile with search_results_path and derived search_history_path."""
from __future__ import annotations

import json
import typing
from pathlib import Path

import search_query

import colrev.exceptions as colrev_exceptions
import colrev.git_repo
from colrev.constants import SearchType


class ExtendedSearchFile(search_query.SearchFile):
    """Extended SearchFile with search_results_path and derived search_history_path."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        search_string: str,
        platform: str,
        search_results_path: Path,
        search_type: SearchType,
        version: str,
        **kwargs: typing.Any,
    ) -> None:

        # Mandatory attribute
        self.search_type = SearchType(search_type)

        if not str(search_results_path).replace("\\", "/").startswith("data/search"):
            raise colrev_exceptions.InvalidSettingsError(
                msg="Source search_results_path does not start with "
                + f"data/search: {search_results_path}"
            )

        super().__init__(
            search_string=search_string,
            platform=platform,
            search_results_path=search_results_path,
            version=version,
            **kwargs,
        )

    def to_dict(self) -> dict:
        """Extend parent to_dict with search_results_path and search_history_path."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "search_results_path": str(self.search_results_path),
                "search_history_path": str(self.get_search_history_path()),
                "search_type": self.search_type.value,
            }
        )
        return base_dict

    # pylint: disable=unused-argument
    def model_dump(self, **kwargs) -> dict:  # type: ignore
        """Dump the search file with search_results_path and search_history_path."""
        return {
            "platform": self.platform,
            "search_results_path": str(self.search_results_path),
            "search_string": self.search_string,
            "search_type": self.search_type.value,
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

    # pylint: disable=unused-argument
    def get_search_history_path(
        self, search_history_path: typing.Optional[str | Path] = None
    ) -> Path:
        """Get the search history path."""
        assert search_history_path is None

        return Path("data/search") / Path(
            Path(self.search_results_path).stem + "_search_history.json"
        )

    def save(
        self,
        search_history_path: typing.Optional[str | Path] = None,
        git_repo: typing.Optional[colrev.git_repo.GitRepo] = None,
    ) -> None:
        """Save the search file to a JSON file."""
        path = (
            Path(search_history_path)
            if search_history_path
            else self.get_search_history_path()
        )
        if path is None:
            raise ValueError(
                "No search_history_path provided and no previous search_history_path stored."
            )
        with open(path, "w", encoding="utf-8") as f:
            mod_dict = self.to_dict()
            mod_dict.pop("search_history_path", None)
            json.dump(mod_dict, f, indent=4, ensure_ascii=False)
        if git_repo:
            git_repo.add_changes(path)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"platform={self.platform!r}, "
            f"search_results_path={str(self.search_results_path)!r}, "
            f"search_type={self.search_type.value!r}, "
            f"version={self.version!r})"
        )

    def __str__(self) -> str:
        try:
            payload = self.to_dict()
        except Exception:
            payload = {
                "platform": self.platform,
                "search_results_path": str(self.search_results_path),
                "search_type": self.search_type.value,
            }

        # Ensure Paths/Enums/sets etc. are serializable
        def _default(o) -> str:  # type: ignore
            from pathlib import Path
            from enum import Enum

            if isinstance(o, Path):
                return str(o)
            if isinstance(o, Enum):
                return o.value
            return str(o)

        return json.dumps(payload, indent=2, ensure_ascii=False, default=_default)


load_search_file = search_query.load_search_file
