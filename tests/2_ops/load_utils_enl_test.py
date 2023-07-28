#!/usr/bin/env python
"""Tests of the enl load utils"""
from pathlib import Path

import colrev.ops.load_utils_enl
import colrev.review_manager
import colrev.settings


def test_load(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the enl load utils"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="load_commit")

    search_source = colrev.settings.SearchSource(
        endpoint="colrev.unknown_source",
        filename=Path("data/search/ais.txt"),
        search_type=colrev.settings.SearchType.OTHER,
        search_parameters={"scope": {"path": "test"}},
        comment="",
    )

    helpers.retrieve_test_file(
        source=Path("load_utils/") / Path("ais.txt"),
        target=Path("data/search/") / Path("ais.txt"),
    )

    records = colrev.ops.load_utils_enl.load(source=search_source)
    expected = (
        helpers.test_data_path / Path("load_utils/") / Path("ais_expected.bib")
    ).read_text(encoding="utf-8")

    actual = base_repo_review_manager.dataset.parse_bibtex_str(recs_dict_in=records)
    print(actual)
    assert actual == expected
