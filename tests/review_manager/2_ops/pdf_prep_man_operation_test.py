#!/usr/bin/env python
"""Tests of the CoLRev pdf-prep-man operation"""
import colrev.review_manager


def test_pdf_prep_man(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the pdf-prep-man operation"""

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="pdf_prep_commit"
    )
    pdf_prep_man_operation = base_repo_review_manager.get_pdf_prep_man_operation()
    pdf_prep_man_operation.main()
    pdf_prep_man_operation.pdf_prep_man_stats()
    pdf_prep_man_operation.extract_needs_pdf_prep_man()
    pdf_prep_man_operation.discard()
