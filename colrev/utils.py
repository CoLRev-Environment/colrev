#! /usr/bin/env python3
"""Utility helpers for CoLRev."""
from __future__ import annotations

import os
import pprint
import re
import typing
import unicodedata
from datetime import timedelta
from pathlib import Path

import inquirer
import requests_cache

import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.constants import SearchType
from colrev.search_file import load_search_file

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
    *,
    base_path: Path,
    file_path_string: str,
    suffix: str = ".bib",
    prefix: str = "data/search/",
) -> Path:
    """Get a unique filename for a (new) SearchSource"""

    base_path = base_path / Path(prefix)
    existing_filenames = []
    for search_file_path in base_path.glob("*_search_history.json"):
        search_file = load_search_file(search_file_path)
        # pylint: disable=protected-access
        existing_filenames.append(search_file.get_search_history_path())
    for existing_file in base_path.glob("*"):
        existing_filenames.append(existing_file)

    file_path_string = (
        file_path_string.replace("+", "_").replace(" ", "_").replace(";", "_")
    )

    if file_path_string.endswith(suffix):
        file_path_string = file_path_string.rstrip(suffix)
    filename = base_path / Path(f"{file_path_string}{suffix}")
    if all(x != filename for x in existing_filenames):
        return Path(prefix) / filename.name

    i = 1
    while not all(x != filename for x in existing_filenames):
        filename = Path(f"{file_path_string}_{i}{suffix}")
        i += 1

    return Path(prefix) / filename.name


def select_search_type(*, search_types: list, params: dict) -> SearchType:
    """Select the SearchType (interactively if neccessary)"""

    if Fields.URL in params:
        return SearchType.API
    if "search_file" in params:
        return SearchType.DB

    choices = [x for x in search_types if x != SearchType.MD]
    if len(choices) == 1:
        return choices[0]
    choices.sort()
    questions = [
        inquirer.List(
            "search_type",
            message="Select SearchType:",
            choices=choices,
        ),
    ]
    answers = inquirer.prompt(questions)
    return SearchType[answers["search_type"]]


def get_project_home_dir(*, path_str: typing.Optional[str] = None) -> Path:
    """Get the root directory of the CoLRev project
    (i.e., the directory containing the .git directory)"""
    if path_str:
        original_dir = Path(path_str)
    else:
        original_dir = Path.cwd()

    while ".git" not in [f.name for f in original_dir.iterdir() if f.is_dir()]:
        if original_dir.parent == original_dir:  # reached root
            break
        original_dir = original_dir.parent

    if original_dir.parent == original_dir:  # reached root
        raise colrev_exceptions.RepoSetupError(
            "Failed to locate a .git directory. "
            "Ensure you are within a Git repository, "
            "or set navigate_to_home_dir=False for init."
        )

    return original_dir


STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "in",
    "on",
    "for",
    "to",
    "with",
    "by",
    "from",
    "at",
    "as",
    "is",
    "are",
    "be",
    "was",
    "were",
    "been",
    "being",
    "into",
    "about",
    "over",
    "under",
    "between",
    "among",
    "via",
    "using",
    "than",
    "that",
    "this",
    "those",
    "these",
    "their",
    "its",
    "it",
    "we",
    "you",
    "your",
    "our",
    "his",
    "her",
}


# Keep letters, digits, and common tech punctuation (+, #, -)
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#-]*")


def _strip_diacritics(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def remove_stopwords(
    input_str: str, stopwords: typing.Optional[typing.Set[str]] = None
) -> str:
    """Remove stopwords from a string"""
    if stopwords is None:
        stopwords = STOPWORDS
    text = _strip_diacritics(input_str)
    tokens = _TOKEN_RE.findall(text)

    kept = []
    for tok in tokens:
        low = tok.lower()
        # drop function-word stopwords (but keep ALLCAPS acronyms)
        if low in stopwords and not tok.isupper():
            continue
        kept.append(tok)

    return " ".join(kept)
