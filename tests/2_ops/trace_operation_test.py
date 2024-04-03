#!/usr/bin/env python
"""Tests of the CoLRev trace operation"""
import colrev.review_manager
import colrev.settings


def test_trace(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the trace operation"""
    helpers.reset_commit(base_repo_review_manager, commit="data_commit")
    trace_operation = base_repo_review_manager.get_trace_operation()

    trace_operation.main(record_id="SrivastavaShainesh2015")

    base_repo_review_manager.verbose_mode = True
    trace_operation.main(record_id="SrivastavaShainesh2015")
