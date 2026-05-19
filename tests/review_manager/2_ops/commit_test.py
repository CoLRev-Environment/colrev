#!/usr/bin/env python
"""Tests of the CoLRev commit operation"""

import git
import pytest
from docker import errors as docker_errors

import colrev.exceptions as colrev_exceptions
import colrev.ops.check
from colrev.ops.commit import Commit


@pytest.fixture(scope="session", name="commit_fixture")
def get_commit_fixture(tmp_path_factory, base_repo_review_manager):  # type: ignore
    """Fixture returning the commit object"""

    review_manager = base_repo_review_manager
    msg = "Test commit"
    manual_author = False
    script_name = "test_script"
    saved_args = {"arg1": "value1", "arg2": "value2"}
    skip_hooks = False

    commit = Commit(
        review_manager=review_manager,
        msg=msg,
        manual_author=manual_author,
        script_name=script_name,
        saved_args=saved_args,
        skip_hooks=skip_hooks,
    )
    return commit


def test_parse_script_name(tmp_path, commit_fixture):  # type: ignore
    script_name = "colrev cli"
    parsed_script_name = commit_fixture._parse_script_name(script_name=script_name)
    assert parsed_script_name == "colrev"


def test_create(commit_fixture, mocker):  # type: ignore

    def patched_has_record_changes() -> bool:
        return True

    mocker.patch(
        "colrev.git_repo.GitRepo.has_record_changes",
        side_effect=patched_has_record_changes,
    )
    colrev.ops.check.CheckOperation(commit_fixture.review_manager)
    records = commit_fixture.review_manager.dataset.load_records_dict()
    records["SrivastavaShainesh2015"]["title"] = "test"
    commit_fixture.review_manager.dataset.save_records_dict(records)
    commit_fixture.review_manager.force_mode = False
    commit_fixture.skip_hooks = True
    with pytest.raises(colrev_exceptions.DirtyRepoAfterProcessingError):
        commit_fixture.create()

    colrev.ops.check.CheckOperation(commit_fixture.review_manager)
    records = commit_fixture.review_manager.dataset.load_records_dict()
    records["SrivastavaShainesh2015"]["title"] = "test2"
    commit_fixture.review_manager.dataset.save_records_dict(records)
    commit_fixture.review_manager.force_mode = False
    commit_fixture.review_manager.force_mode = True
    commit_fixture.create()


def test_get_git_version_success(commit_fixture, mocker):  # type: ignore
    mocker.patch("colrev.ops.commit.shutil.which", return_value="/usr/bin/git")
    mocker.patch("colrev.ops.commit.git.refresh")
    mocker.patch(
        "colrev.ops.commit.git.cmd.Git.version_info",
        new_callable=mocker.PropertyMock,
        return_value=(2, 44, 0),
    )

    assert commit_fixture._get_git_version() == "version 2.44.0"


def test_get_git_version_failure(commit_fixture, mocker):  # type: ignore
    mocker.patch("colrev.ops.commit.shutil.which", return_value="/usr/bin/git")
    mocker.patch("colrev.ops.commit.git.refresh", side_effect=git.exc.GitError("err"))

    assert commit_fixture._get_git_version() == "Not installed"


def test_get_docker_version_success(commit_fixture, mocker):  # type: ignore
    docker_client = mocker.MagicMock()
    docker_client.version.return_value = {"Version": "27.1.0"}
    mocker.patch("colrev.ops.commit.docker_from_env", return_value=docker_client)

    assert commit_fixture._get_docker_version() == "version 27.1.0"
    docker_client.close.assert_called_once()


def test_get_docker_version_failure(commit_fixture, mocker):  # type: ignore
    mocker.patch(
        "colrev.ops.commit.docker_from_env",
        side_effect=docker_errors.DockerException("unavailable"),
    )

    assert commit_fixture._get_docker_version() == "Not installed"
