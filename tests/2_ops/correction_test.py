#!/usr/bin/env python
"""Tests of the CoLRev corrections"""
from pathlib import Path

import git
import pytest

import colrev.ops.correct
import colrev.review_manager


@pytest.fixture(scope="function", name="correction_fixture")
def get_correction_fixture(base_repo_review_manager):  # type: ignore
    """Fixture returning the test_local_index_dir"""
    base_repo_review_manager.get_validate_operation()

    base_repo_review_manager.settings.sources[0].endpoint = "colrev.local_index"
    base_repo_review_manager.save_settings()

    records = base_repo_review_manager.dataset.load_records_dict()
    records["SrivastavaShainesh2015"]["colrev_masterdata_provenance"] = {
        "CURATED": {"source": "url...", "note": ""}
    }
    base_repo_review_manager.dataset.save_records_dict(records)
    base_repo_review_manager.dataset.create_commit(msg="switch to curated")

    records["SrivastavaShainesh2015"]["title"] = "Changed-title"
    base_repo_review_manager.dataset.save_records_dict(records)


def test_corrections(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, correction_fixture
) -> None:
    """Test the corrections"""
    corrections_operation = colrev.ops.correct.Corrections(
        review_manager=base_repo_review_manager
    )
    corrections_operation.check_corrections_of_records()


def test_corrections_pre_commit_hooks(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
    correction_fixture,
) -> None:
    """Test the corrections (triggered by pre-commit hooks)"""

    # Note: corrections (hooks) are not created with the create_commit methods of GitPython
    ret = git.Git(str(base_repo_review_manager.path)).execute(
        ["git", "commit", "-m", "test"]
    )
    print(ret)
    base_repo_review_manager.dataset.get_repo().git.log(p=True)
    corrections_path = base_repo_review_manager.paths.corrections

    expected = (
        helpers.test_data_path
        / Path("data/corrections")
        / Path("SrivastavaShainesh2015.json")
    ).read_text(encoding="utf-8")
    actual = (corrections_path / Path("SrivastavaShainesh2015.json")).read_text(
        encoding="utf-8"
    )
    assert expected == actual
