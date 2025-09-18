#!/usr/bin/env python
"""Tests of the CoLRev check operation"""
import pytest

import colrev.exceptions as colrev_exceptions
import colrev.review_manager
from colrev.process.model import ProcessModel


def test_check_operation_precondition(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the check operation preconditions"""

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="changed_settings_commit"
    )

    dedupe_operation = base_repo_review_manager.get_dedupe_operation()
    dedupe_operation.review_manager.settings.project.delay_automated_processing = True

    with pytest.raises(colrev_exceptions.NoRecordsError):
        ProcessModel.check_operation_precondition(dedupe_operation)

    review_manager_helpers.reset_commit(base_repo_review_manager, commit="prep_commit")

    prescreen_operation = base_repo_review_manager.get_prescreen_operation()
    prescreen_operation.review_manager.settings.project.delay_automated_processing = (
        True
    )

    with pytest.raises(colrev_exceptions.ProcessOrderViolation):
        ProcessModel.check_operation_precondition(prescreen_operation)
    prescreen_operation.review_manager.settings.project.delay_automated_processing = (
        False
    )
