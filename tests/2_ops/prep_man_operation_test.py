#!/usr/bin/env python
"""Tests of the CoLRev prep-man operation"""
import colrev.review_manager


def test_prep_man(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the prep-man operation"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="prep_commit")
    prep_man_operation = base_repo_review_manager.get_prep_man_operation()
    prep_man_operation.prep_man_stats()
    prep_man_operation.main()
