#!/usr/bin/env python
"""Tests for the review_manager"""
import tempfile
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.review_manager
from colrev.constants import Colors

# flake8: noqa: E501


def test_invalid_git_repository_error(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Test handling of InvalidGitRepositoryError when initializing ReviewManager with an invalid repo path."""

    with pytest.raises(colrev_exceptions.RepoSetupError):
        colrev.review_manager.ReviewManager(path_str=str(tmp_path))

    report_log_path = tmp_path / ".report.log"
    report_log_path.touch()
    with pytest.raises(colrev_exceptions.RepoSetupError):
        colrev.review_manager.ReviewManager(path_str=str(tmp_path))

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    with pytest.raises(colrev_exceptions.RepoSetupError):
        colrev.review_manager.ReviewManager(path_str=str(tmp_path))

    settings_path = tmp_path / "settings.json"
    settings_path.touch()
    with pytest.raises(colrev.exceptions.RepoSetupError):
        colrev.review_manager.ReviewManager(path_str=str(tmp_path))


def test_in_test_environment(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    assert base_repo_review_manager.in_test_environment()


def test_report(base_repo_review_manager: colrev.review_manager.ReviewManager) -> None:
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as temp_file:
        with open(temp_file.name, "w", encoding="utf-8") as file:
            file.write("Test")
        base_repo_review_manager.report(msg_file=Path(temp_file.name))


def test_get_colrev_versions(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    colrev_versions = base_repo_review_manager.get_colrev_versions()
    assert ["0.12.3", "0.12.3"] == colrev_versions, print(
        f"To install the current version, run {Colors.ORANGE}pip install -e .{Colors.END}"
    )


def test_check_repository_setup(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    base_repo_review_manager.check_repository_setup()


def test_check_repo(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    base_repo_review_manager.check_repo()


def test__check_update(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    base_repo_review_manager._check_update()


def test_update_config(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    base_repo_review_manager.update_config()


def test_sharing(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    ret = base_repo_review_manager.sharing()
    assert not ret["status"]
    assert "Project not yet shared" in ret["msg"]
