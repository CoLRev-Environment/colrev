"""Tests for pruning origins against search result feeds."""

# pylint: disable=protected-access

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import colrev.review_manager
from colrev.ops import repare
from colrev.constants import Fields


def _repare_with_sources(sources: list) -> repare.Repare:
    operation = repare.Repare.__new__(repare.Repare)
    operation.review_manager = cast(
        colrev.review_manager.ReviewManager,
        SimpleNamespace(
            settings=SimpleNamespace(sources=sources),
            logger=logging.getLogger(__name__),
        ),
    )
    return operation


def test_remove_records_not_in_search_results_prunes_only_missing_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loaded feed IDs are used to prune missing origins."""
    source = SimpleNamespace(
        get_origin_prefix=lambda: "feed.bib",
        search_results_path=Path("data/search/feed.bib"),
    )
    monkeypatch.setattr(repare, "load_primary", lambda *_args, **_kwargs: {"keep": {}})
    operation = _repare_with_sources([source])
    records = {
        "record": {
            Fields.ID: "record",
            Fields.ORIGIN: ["feed.bib/keep", "feed.bib/missing"],
        }
    }

    operation._remove_records_not_in_search_results(records)

    assert records["record"][Fields.ORIGIN] == ["feed.bib/keep"]


def test_remove_records_not_in_search_results_preserves_origins_on_load_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreadable or malformed feeds cannot justify deleting their origins."""
    source = SimpleNamespace(
        get_origin_prefix=lambda: "feed.bib",
        search_results_path=Path("data/search/feed.bib"),
    )
    monkeypatch.setattr(
        repare,
        "load_primary",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("invalid BibTeX")),
    )
    operation = _repare_with_sources([source])
    records = {
        "record": {
            Fields.ID: "record",
            Fields.ORIGIN: ["feed.bib/possibly-valid"],
        }
    }

    operation._remove_records_not_in_search_results(records)

    assert records["record"][Fields.ORIGIN] == ["feed.bib/possibly-valid"]


def test_remove_records_not_in_search_results_skips_invalid_origin_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source with an invalid origin prefix is left unverifiable, not pruned."""
    source = SimpleNamespace(
        get_origin_prefix=lambda: (_ for _ in ()).throw(
            AssertionError("invalid source filename")
        ),
        search_results_path=Path("data/search/feed.bib"),
    )
    monkeypatch.setattr(
        repare,
        "load_primary",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not load invalid source")
        ),
    )
    operation = _repare_with_sources([source])
    records = {
        "record": {
            Fields.ID: "record",
            Fields.ORIGIN: ["feed.bib/possibly-valid"],
        }
    }

    operation._remove_records_not_in_search_results(records)

    assert records["record"][Fields.ORIGIN] == ["feed.bib/possibly-valid"]
