#!/usr/bin/env python
"""Tests of the CoLRev dedupe operation"""
import shutil
import typing
from pathlib import Path

import pytest

import colrev.review_manager


@pytest.fixture(scope="session", name="dedupe_test_setup")
def fixture_quality_model(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> colrev.review_manager.ReviewManager:
    """Fixture returning the dedupe_test_setup"""
    helpers.reset_commit(review_manager=base_repo_review_manager, commit="prep_commit")

    helpers.retrieve_test_file(
        source=Path("dedupe/records.bib"),
        target=Path("data/records.bib"),
    )
    base_repo_review_manager.dataset.add_changes(path=Path("data/records.bib"))
    base_repo_review_manager.create_commit(
        msg="Import dedupe test cases", manual_author=True
    )
    return base_repo_review_manager


def test_dedupe(  # type: ignore
    dedupe_test_setup: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the dedupe operation"""

    # TODO : this should test individual methods (main/dedupe package is tested separately...)

    dedupe_operation = dedupe_test_setup.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.review_manager.verbose_mode = True
    dedupe_operation.main()

    dedupe_operation.unmerge_records(previous_id_lists=[["Staehr2010", "Staehr2010a"]])
    dedupe_test_setup.dataset.add_changes(path=Path("data/records.bib"))
    dedupe_test_setup.create_commit(
        msg="Unmerge Staehr2010-Staehr2010a", manual_author=True
    )

    dedupe_operation.merge_records(
        merge="30_example_records.bib/Staehr2010,30_example_records.bib/Staehr2010a"
    )
    dedupe_test_setup.dataset.add_changes(path=Path("data/records.bib"))
    dedupe_test_setup.create_commit(
        msg="Merge Staehr2010-Staehr2010a", manual_author=True
    )

    expected_file = Path("dedupe/records_expected.bib")
    actual = Path("data/records.bib").read_text(encoding="utf-8")
    if (helpers.test_data_path / expected_file).is_file():
        expected = (helpers.test_data_path / expected_file).read_text(encoding="utf-8")
    else:
        expected = ""

    # If mismatch: copy the actual file to replace the expected file (facilitating updates)
    if expected != actual:
        print(Path.cwd())
        shutil.copy(
            Path("data/records.bib"),
            helpers.test_data_path / Path("dedupe/records_expected.bib"),
        )
        if not (helpers.test_data_path / expected_file).is_file():
            raise Exception(
                f"The expected_file ({expected_file.name}) was not (yet) available. "
                f"An initial version was created in {expected_file}. "
                "Please check, update, and add/commit it. Afterwards, rerun the tests."
            )
        raise Exception(
            f"Updated the expected_file ({expected_file.name}) based on the expected data."
        )

    assert expected == actual


def test_dedupe_skip_prescreen(
    dedupe_test_setup: colrev.review_manager.ReviewManager,
) -> None:
    """Test the skipping of prescreens after the dedupe operation"""

    dedupe_operation = dedupe_test_setup.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_test_setup.settings.prescreen.prescreen_package_endpoints = []
    dedupe_operation.main()
    # TODO : add testing of results


def test_dedupe_get_info(
    dedupe_test_setup: colrev.review_manager.ReviewManager,
) -> None:
    """Test the get_info of dedupe"""

    dedupe_operation = dedupe_test_setup.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    actual = dedupe_operation.get_info()
    expected: typing.Dict[str, typing.Any] = {"same_source_merges": []}

    assert expected == actual
