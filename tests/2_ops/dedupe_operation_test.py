#!/usr/bin/env python
"""Tests of the CoLRev dedupe operation"""
import colrev.review_manager


def test_dedupe(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the dedupe operation"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="prep_commit")

    # dedupe_operation = base_repo_review_manager.get_dedupe_operation(
    #     notify_state_transition_operation=True
    # )
    # dedupe_operation.main()
