#!/usr/bin/env python
"""Tests of the CoLRev prep operation"""
import colrev.review_manager


def test_prep(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the prep operation"""

    review_manager_helpers.reset_commit(base_repo_review_manager, commit="load_commit")

    base_repo_review_manager.verbose_mode = True
    prep_operation = base_repo_review_manager.get_prep_operation()
    prep_operation.main()


def test_prep_set_id(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test prep set_id"""

    prep_operation = base_repo_review_manager.get_prep_operation()
    prep_operation.set_ids()


def test_prep_setup_custom_script(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test prep setup_custom_script"""

    prep_operation = base_repo_review_manager.get_prep_operation()
    prep_operation.setup_custom_script()


def test_prep_with_polish_flag(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test prep operation with polish flag"""

    # Using helper to checkout to the specific commit for pdf-get
    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="pdf_get_commit"
    )

    # Setting up the prep operation with polish flag
    prep_operation = base_repo_review_manager.get_prep_operation(polish=True)
    prep_operation.main()

    # Assertions can be added here based on expected outcomes
