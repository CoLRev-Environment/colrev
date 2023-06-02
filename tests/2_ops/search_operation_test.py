#!/usr/bin/env python
"""Tests of the CoLRev search operation"""
from pathlib import Path

import colrev.review_manager
import colrev.settings
from unittest.mock import patch

@patch("colrev.review_manager.ReviewManager.in_ci_environment")
def test_search(ci_env_patcher, base_repo_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the search operation"""

    ci_env_patcher.return_value = True

    search_operation = base_repo_review_manager.get_search_operation()
    # base_repo_review_manager.settings.sources.append()
    search_operation.main(rerun=True)

    search_operation.view_sources()


def test_search_add_source(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, mocker
) -> None:
    """Test the search add_source"""

    search_operation = base_repo_review_manager.get_search_operation()
    add_source = colrev.settings.SearchSource(
        endpoint="colrev.crossref",
        filename=(
            base_repo_review_manager.path / Path("data/search/crossref_search.bib")
        ),
        search_type=colrev.settings.SearchType.DB,
        search_parameters={"query": "test"},
        load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
        comment="",
    )

    with mocker.patch.object(
        colrev.ops.search.Search,
        "main",
        return_value=10,
    ):
        # patch search_operation.main
        search_operation.add_source(add_source=add_source)


def test_search_get_unique_filename(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the search.get_unique_filename()"""

    search_operation = base_repo_review_manager.get_search_operation()
    expected = Path("data/search/test_records_1.bib")
    actual = search_operation.get_unique_filename(file_path_string="test_records.bib")
    print(actual)
    assert expected == actual


def test_prep_setup_custom_script(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test search setup_custom_script"""

    search_operation = base_repo_review_manager.get_search_operation()
    search_operation.setup_custom_script()
