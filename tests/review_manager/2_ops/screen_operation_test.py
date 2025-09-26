#!/usr/bin/env python
"""Tests of the CoLRev screen operation"""
import pytest

import colrev.review_manager
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.constants import ScreenCriterionType


@pytest.fixture(scope="package", name="criterion")
def criterion_fixture() -> colrev.settings.ScreenCriterion:
    """Fixture returning an criterion"""

    criterion = colrev.settings.ScreenCriterion(
        explanation="Explanation of the criterion",
        criterion_type=ScreenCriterionType["inclusion_criterion"],
        comment="",
    )
    return criterion


def test_screen(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the screen operation"""

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="screen_commit"
    )
    screen_operation = base_repo_review_manager.get_screen_operation()
    screen_operation.include_all_in_screen(persist=False)
    screen_operation.create_screen_split(create_split=2)
    screen_operation.setup_custom_script()

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="screen_commit"
    )


def test_add_criterion(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, criterion
) -> None:
    """Test adding a screening criterion"""
    screen_operation = base_repo_review_manager.get_screen_operation()
    criterion_name = "new_criterion"
    screen_operation.add_criterion(criterion_name=criterion_name, criterion=criterion)

    # Verify the criterion was added
    assert criterion_name in base_repo_review_manager.settings.screen.criteria


def test_delete_criterion(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, criterion
) -> None:
    """Test deleting a screening criterion"""
    criterion_to_delete = "existing_criterion"
    # Pre-add a criterion to ensure it can be deleted
    base_repo_review_manager.settings.screen.criteria[criterion_to_delete] = criterion
    screen_operation = base_repo_review_manager.get_screen_operation()
    screen_operation.delete_criterion(criterion_to_delete=criterion_to_delete)

    # Verify the criterion was deleted
    assert criterion_to_delete not in base_repo_review_manager.settings.screen.criteria


def test_to_screen(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    screen_operation = base_repo_review_manager.get_screen_operation()

    assert screen_operation.to_screen({Fields.STATUS: RecordState.pdf_prepared})

    assert not screen_operation.to_screen({Fields.STATUS: RecordState.md_processed})

    assert not screen_operation.to_screen(
        {
            Fields.STATUS: RecordState.rev_synthesized,
            Fields.SCREENING_CRITERIA: "focus_hr=in",
        }
    )
    assert screen_operation.to_screen(
        {
            Fields.STATUS: RecordState.rev_synthesized,
            Fields.SCREENING_CRITERIA: "focus_hr=TODO",
        }
    )
