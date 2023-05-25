#!/usr/bin/env python
"""Tests of the CoLRev data operation"""
import colrev.review_manager


def test_data(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the date operation"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="data_commit")
    data_operation = base_repo_review_manager.get_data_operation()
    data_operation.profile()

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="data_commit")
    data_operation.setup_custom_script()

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="data_commit")
    base_repo_review_manager.load_settings()
