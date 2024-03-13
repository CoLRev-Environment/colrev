#!/usr/bin/env python
"""Tests of the CoLRev check operation"""
import pytest

import colrev.exceptions as colrev_exceptions
import colrev.review_manager
from colrev.record import RecordStateModel


def test_check_operation_precondition(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the check operation preconditions"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="load_commit")

    dedupe_operation = base_repo_review_manager.get_dedupe_operation()
    dedupe_operation.review_manager.settings.project.delay_automated_processing = True
    with pytest.raises(colrev_exceptions.ProcessOrderViolation):
        RecordStateModel.check_operation_precondition(operation=dedupe_operation)
    dedupe_operation.review_manager.settings.project.delay_automated_processing = False
