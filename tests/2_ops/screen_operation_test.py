#!/usr/bin/env python
"""Tests of the CoLRev screen operation"""
import colrev.review_manager


def test_screen(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the screen operation"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="screen_commit"
    )
    screen_operation = base_repo_review_manager.get_screen_operation()
    # base_repo_review_manager.settings.screen.screen_package_endpoints = []
    # screen_operation.main(split_str="NA")
    screen_operation.include_all_in_screen(persist=False)
    screen_operation.create_screen_split(create_split=2)

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="screen_commit"
    )
    screen_operation.setup_custom_script()
