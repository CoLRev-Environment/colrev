#! /usr/bin/env python3
"""Utility helpers for CoLRev."""
from __future__ import annotations

import os
import pprint
import typing
from datetime import timedelta
from pathlib import Path

import requests_cache

from colrev.constants import Filepaths

_p_printer = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def pformat(obj: typing.Any) -> str:
    """Return a pretty-formatted representation of ``obj``."""
    return _p_printer.pformat(obj)


def p_print(obj: typing.Any) -> None:
    """Pretty-print ``obj`` using repository defaults."""
    _p_printer.pprint(obj)


def get_cached_session() -> requests_cache.CachedSession:  # pragma: no cover
    """Get a cached session"""

    return requests_cache.CachedSession(
        str(Filepaths.PREP_REQUESTS_CACHE_FILE),
        backend="sqlite",
        expire_after=timedelta(days=30),
    )


def in_ci_environment() -> bool:
    """Return True if running in a CI environment (e.g., GitHub Actions)."""

    identifier_list = ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    return any("true" == os.getenv(x) for x in identifier_list)


def get_unique_filename(
    *, review_manager, file_path_string: str, suffix: str = ".bib"
) -> Path:
    """Get a unique filename for a (new) SearchSource"""

    review_manager.load_settings()
    sources = review_manager.settings.sources

    file_path_string = (
        file_path_string.replace("+", "_").replace(" ", "_").replace(";", "_")
    )

    if file_path_string.endswith(suffix):
        file_path_string = file_path_string.rstrip(suffix)
    filename = Path(f"data/search/{file_path_string}{suffix}")
    existing_filenames = [x.search_results_path for x in sources]
    if all(x != filename for x in existing_filenames):
        return filename

    i = 1
    while not all(x != filename for x in existing_filenames):
        filename = Path(f"data/search/{file_path_string}_{i}{suffix}")
        i += 1

    return filename
