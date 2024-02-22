#!/usr/bin/env python
"""Tests for the review_manager"""
import json

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.review_manager

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
    with pytest.raises(json.decoder.JSONDecodeError):
        colrev.review_manager.ReviewManager(path_str=str(tmp_path))
