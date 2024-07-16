#!/usr/bin/env python
"""Tests of the CoLRev data operation"""
import colrev.review_manager


def test_data_custom_script(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the date setup custom script"""

    data_operation = base_repo_review_manager.get_data_operation()
    data_operation.setup_custom_script()
