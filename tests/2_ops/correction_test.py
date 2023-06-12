#!/usr/bin/env python
"""Tests of the CoLRev corrections"""
import git

import colrev.review_manager
import colrev.settings


def test_corrections(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the corrections"""
    helpers.reset_commit(review_manager=base_repo_review_manager, commit="data_commit")
    base_repo_review_manager.get_validate_operation()

    base_repo_review_manager.settings.sources[0].endpoint = "colrev.local_index"
    base_repo_review_manager.save_settings()

    records = base_repo_review_manager.dataset.load_records_dict()
    records["SrivastavaShainesh2015"]["colrev_masterdata_provenance"] = {
        "CURATED": {"source": "url...", "note": ""}
    }
    base_repo_review_manager.dataset.save_records_dict(records=records)
    base_repo_review_manager.dataset.add_record_changes()
    base_repo_review_manager.create_commit(msg="switch to curated")

    records["SrivastavaShainesh2015"]["title"] = "Changed-title"
    base_repo_review_manager.dataset.save_records_dict(records=records)
    base_repo_review_manager.dataset.add_record_changes()

    # Note: corrections (hooks) are not created with the create_commit methods
    git.Git(str(base_repo_review_manager.path)).execute(["git", "commit", "-m", "test"])
    base_repo_review_manager.dataset.get_repo().git.log(p=True)
    # print(base_repo_review_manager.corrections_path.is_dir())
    # print(base_repo_review_manager.dataset.get_repo().head.commit.message)

    # expected = (
    #     helpers.test_data_path
    #     / Path("corrections")
    #     / Path("SrivastavaShainesh2015.json")
    # ).read_text(encoding="utf-8")
    # actual = (
    #     base_repo_review_manager.corrections_path / Path("SrivastavaShainesh2015.json")
    # ).read_text(encoding="utf-8")
    # assert expected == actual
