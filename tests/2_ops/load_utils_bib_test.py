#!/usr/bin/env python
"""Tests of the load utils for bib files"""
from pathlib import Path

import colrev.ops.load_utils_bib
import colrev.review_manager
import colrev.settings


def test_load(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the load utils for bib files"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="load_commit")

    search_source = colrev.settings.SearchSource(
        endpoint="colrev.unknown_source",
        filename=Path("data/search/bib_tests.bib"),
        search_type=colrev.settings.SearchType.OTHER,
        search_parameters={"scope": {"path": "test"}},
        comment="",
    )

    helpers.retrieve_test_file(
        source=Path("load_utils/") / Path("bib_tests.bib"),
        target=Path("data/search/") / Path("bib_tests.bib"),
    )
    load_operation = base_repo_review_manager.get_load_operation()

    loader = colrev.ops.load_utils_bib.BIBLoader(
        load_operation=load_operation,
        source=search_source,
        list_fields={},
        unique_id_field=""
    )
    records = loader.load_bib_file()
    expected = (
        helpers.test_data_path / Path("load_utils/") / Path("bib_tests_expected.bib")
    ).read_text(encoding="utf-8")

    actual = base_repo_review_manager.dataset.parse_bibtex_str(recs_dict_in=records)
    assert actual == expected
