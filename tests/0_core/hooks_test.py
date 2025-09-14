#!/usr/bin/env python
"""Tests for the review_manager"""
import colrev.hooks.check
import colrev.hooks.share
import colrev.review_manager

# flake8: noqa: E501


def test_check_repo(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    colrev.hooks.check.main()


def test_sharing(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    ret = colrev.hooks.share.main()
    assert not ret
    # assert not ret["status"]
    # assert "Project not yet shared" in ret["msg"]


# def test_report(base_repo_review_manager: colrev.review_manager.ReviewManager) -> None:
#     with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as temp_file:
#         with open(temp_file.name, "w", encoding="utf-8") as file:
#             file.write("Test")
#         #msg_file=Path(temp_file.name)
#         colrev.hooks.report.main()
