#!/usr/bin/env python
"""Tests of the CoLRev status operation"""
import colrev.review_manager


def test_get_analytics(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the prescreen operation"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="dedupe_commit"
    )

    status_operation = base_repo_review_manager.get_status_operation()
    ret = status_operation.get_analytics()

    for details in ret.values():
        details.pop("commit_id", None)
        details.pop("committed_date", None)

    assert ret == {
        5: {
            "atomic_steps": 8,
            "completed_atomic_steps": 2,
            "commit_author": "script: -s test_records.bib",
            "search": 1,
            "included": 0,
        },
        4: {
            "atomic_steps": 8,
            "completed_atomic_steps": 1,
            "commit_author": "script: -s test_records.bib",
            "search": 1,
            "included": 0,
        },
        3: {
            "atomic_steps": 8,
            "completed_atomic_steps": 0,
            "commit_author": "script: -s test_records.bib",
            "search": 1,
            "included": 0,
        },
        2: {
            "atomic_steps": 8,
            "completed_atomic_steps": 0,
            "commit_author": "Tester Name",
            "search": 1,
            "included": 0,
        },
        1: {
            "atomic_steps": 0,
            "completed_atomic_steps": 0,
            "commit_author": "Tester Name",
            "search": 0,
            "included": 0,
        },
    }


def test_status_stats(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    colrev.operation.CheckOperation(base_repo_review_manager)

    records = base_repo_review_manager.dataset.load_records_dict()
    status_stats = base_repo_review_manager.get_status_stats(records=records)
    print(status_stats)
    assert status_stats.atomic_steps == 8
