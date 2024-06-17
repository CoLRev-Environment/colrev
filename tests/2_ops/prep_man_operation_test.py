#!/usr/bin/env python
"""Tests of the CoLRev prep-man operation"""
import shutil
from unittest.mock import patch

import colrev.review_manager


def test_prep_man(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the prep-man operation"""

    helpers.reset_commit(base_repo_review_manager, commit="prep_commit")
    prep_man_operation = base_repo_review_manager.get_prep_man_operation()
    prep_man_operation.prep_man_stats()
    prep_man_operation.main()


@patch("platform.system")
def test_prep_man_excel_on_windows(  # type: ignore
    platform_patcher,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    """Test the prep-man operation generating excel on windows"""

    # clear files
    shutil.rmtree(base_repo_review_manager.paths.prep, ignore_errors=True)
    base_repo_review_manager.paths.prep.mkdir(parents=True)
    # On Windows it should create an Excel file
    platform_patcher.return_value = "Windows"
    test_prep_man(base_repo_review_manager, helpers)
    path = base_repo_review_manager.paths.prep / "records_prep_man_info.xlsx"
    assert path.exists()


@patch("platform.system")
def test_prep_man_csv_on_linux(  # type: ignore
    platform_patcher,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    """Test the prep-man operation generating csv on Linux"""

    shutil.rmtree(base_repo_review_manager.paths.prep, ignore_errors=True)
    base_repo_review_manager.paths.prep.mkdir(parents=True)
    platform_patcher.return_value = "Linux"
    test_prep_man(base_repo_review_manager, helpers)
    path = base_repo_review_manager.paths.prep / "records_prep_man_info.csv"
    assert path.exists()
