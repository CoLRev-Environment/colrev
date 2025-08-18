#!/usr/bin/env python
"""Tests of the CoLRev commit operation"""
import pytest

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
