#!/usr/bin/env python
"""Tests of the CoLRev pdf-prep operations"""
import colrev.review_manager


def test_pdf_prep(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the pdf-prep operation"""

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="pdf_get_commit"
    )
    pdf_prep_operation = base_repo_review_manager.get_pdf_prep_operation(
        reprocess=False
    )
    pdf_prep_operation.main(batch_size=0)


def test_pdf_discard(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the pdfs --discard"""

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="pdf_prep_commit"
    )
    pdf_get_man_operation = base_repo_review_manager.get_pdf_get_man_operation()
    pdf_get_man_operation.discard()
