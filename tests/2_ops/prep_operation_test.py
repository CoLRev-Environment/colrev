#!/usr/bin/env python
"""Tests of the CoLRev prep operation"""
import colrev.review_manager


def test_prep(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the prep operation"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="load_commit")

    prep_operation = base_repo_review_manager.get_prep_operation()
    prep_operation.skip_prep()

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="prep_commit")

    prep_operation.set_ids()
    # TODO : difference set_ids - reset_ids?
    prep_operation.setup_custom_script()
    prep_operation.reset_ids()
