#!/usr/bin/env python
"""Tests of the CoLRev status operation"""
from pathlib import Path

import colrev.ops.check
import colrev.review_manager


def test_get_analytics(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    """Test the prescreen operation"""

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="dedupe_commit"
    )

    status_operation = base_repo_review_manager.get_status_operation()
    ret = status_operation.get_analytics()

    for details in ret.values():
        details.pop("commit_id", None)
        details.pop("committed_date", None)

    assert ret == {
        5: {
            "atomic_steps": 9,
            "completed_atomic_steps": 4,
            "commit_author": "script:",
            "commit_message": "Dedupe: merge duplicate records",
            "search": 1,
            "included": 0,
        },
        4: {
            "atomic_steps": 9,
            "completed_atomic_steps": 3,
            "commit_author": "script:",
            "commit_message": "Prep: improve record metadata",
            "search": 1,
            "included": 0,
        },
        3: {
            "atomic_steps": 9,
            "completed_atomic_steps": 2,
            "commit_author": "script:",
            "commit_message": "Load: data/search/test_records.bib → data/records.bib",
            "search": 1,
            "included": 0,
        },
        2: {
            "atomic_steps": 9,
            "completed_atomic_steps": 1,
            "commit_author": "Tester Name",
            "commit_message": "add test_records.bib",
            "search": 1,
            "included": 0,
        },
        1: {
            "atomic_steps": 0,
            "completed_atomic_steps": 0,
            "commit_author": "Tester Name",
            "commit_message": "Init: Create CoLRev repository",
            "search": 0,
            "included": 0,
        },
    }


def test_status_stats(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    colrev.ops.check.CheckOperation(base_repo_review_manager)

    records = base_repo_review_manager.dataset.load_records_dict()
    status_stats = base_repo_review_manager.get_status_stats(records=records)
    print(status_stats)
    assert status_stats.atomic_steps == 9


def test_get_review_status_report(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
    helpers,
) -> None:
    """Test the prescreen operation"""

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="dedupe_commit"
    )

    status_operation = base_repo_review_manager.get_status_operation()
    ret = status_operation.get_review_status_report(colors=True)
    expected = helpers.retrieve_test_file_content(
        source=Path("data/status_report_expected.txt")
    )
    assert ret == expected
