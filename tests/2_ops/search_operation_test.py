#!/usr/bin/env python
"""Tests of the CoLRev search operation"""
from pathlib import Path

import colrev.review_manager


def test_search(base_repo_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the search operation"""

    search_operation = base_repo_review_manager.get_search_operation()
    search_operation.main(rerun=True)

    search_operation.view_sources()


def test_search_get_unique_filename(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the search.get_unique_filename()"""

    search_operation = base_repo_review_manager.get_search_operation()
    expected = Path("data/search/test_records_1.bib")
    actual = search_operation.get_unique_filename(file_path_string="test_records.bib")
    print(actual)
    assert expected == actual
