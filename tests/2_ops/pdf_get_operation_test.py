#!/usr/bin/env python
"""Tests of the CoLRev pdf-get operation"""
import colrev.review_manager


def test_pdf_get(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the pdf-get operation"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="prescreen_commit"
    )

    # pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
    #     notify_state_transition_operation=True
    # )
    # pdf_get_operation.main()
