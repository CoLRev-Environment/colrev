#!/usr/bin/env python
"""Tests of the CoLRev prescreen operation"""
import colrev.review_manager


def test_prescreen(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the prescreen operation"""

    review_manager_helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="dedupe_commit"
    )

    prescreen_operation = base_repo_review_manager.get_prescreen_operation()
    prescreen_operation.create_prescreen_split(create_split=2)
    prescreen_operation.include_all_in_prescreen(persist=False)

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="dedupe_commit"
    )
    prescreen_operation.setup_custom_script()
