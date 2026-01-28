#!/usr/bin/env python
"""Tests of the CoLRev dedupe operation"""

import difflib
import shutil
from pathlib import Path

import pytest

import colrev.record.record
import colrev.review_manager
from colrev.constants import Fields
from colrev.ops.dedupe import same_source_merge


@pytest.fixture(scope="session", name="dedupe_test_setup")
def fixture_dedupe_test_setup(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
    helpers,
) -> colrev.review_manager.ReviewManager:
    """Fixture returning the dedupe_test_setup"""
    review_manager_helpers.reset_commit(base_repo_review_manager, commit="prep_commit")

    helpers.retrieve_test_file(
        source=Path("data/dedupe/records.bib"),
        target=Path("data/records.bib"),
    )
    base_repo_review_manager.dataset.git_repo.add_changes(Path("data/records.bib"))
    base_repo_review_manager.create_commit(
        msg="Import dedupe test cases", manual_author=True
    )

    return base_repo_review_manager


def test_dedupe_utilities(  # type: ignore
    dedupe_test_setup: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the dedupe operation"""

    # TODO : this should test individual methods (main/dedupe package is tested separately...)

    dedupe_operation = dedupe_test_setup.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.review_manager.verbose_mode = True
    dedupe_operation.main()

    dedupe_operation.unmerge_records(current_record_ids=["Staehr2010"])
    records = dedupe_test_setup.dataset.load_records_dict()
    assert "Staehr2010" in records.keys()
    assert "Staehr2010a" in records.keys()

    dedupe_test_setup.dataset.git_repo.add_changes(Path("data/records.bib"))
    dedupe_test_setup.dataset.git_repo.create_commit(
        msg="Unmerge Staehr2010-Staehr2010a",
        manual_author=True,
        skip_hooks=True,
        review_manager=dedupe_operation.review_manager,
    )
    dedupe_operation.merge_records(merge=[["Staehr2010", "Staehr2010a"]])
    dedupe_test_setup.dataset.git_repo.add_changes(Path("data/records.bib"))
    dedupe_test_setup.dataset.git_repo.create_commit(
        msg="Merge Staehr2010-Staehr2010a",
        manual_author=True,
        skip_hooks=True,
        review_manager=dedupe_operation.review_manager,
    )
    records = dedupe_test_setup.dataset.load_records_dict()
    assert "Staehr2010" in records.keys()
    assert "Staehr2010a" not in records.keys()

    # Try non-unique ID lists
    dedupe_operation.merge_records(merge=[["Staehr2010", "Staehr2010"]])

    with pytest.raises(AssertionError):
        dedupe_operation.merge_records(merge=[["RandomID1", "RandomID2"]])

    expected_file = Path("data/dedupe/records_expected.bib")
    actual = Path("data/records.bib").read_text(encoding="utf-8")
    if (helpers.test_data_path / expected_file).is_file():
        expected = (helpers.test_data_path / expected_file).read_text(encoding="utf-8")
    else:
        expected = ""

    # If mismatch: copy the actual file to replace the expected file (facilitating updates)
    if expected != actual:
        diff = difflib.unified_diff(expected.splitlines(), actual.splitlines())
        print("\n".join(diff))

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


def _rec(origins: list[str]) -> colrev.record.record.Record:
    """Helper to build a minimal Record with ORIGIN set."""
    return colrev.record.record.Record(data={Fields.ORIGIN: origins})


@pytest.mark.parametrize(
    "main_origins, dupe_origins, expected",
    [
        # no overlap in source prefixes -> False
        (["wos/0001"], ["scopus/0002"], False),
        # overlap with non-md_ source prefix -> True
        (["wos/0001"], ["wos/0009"], True),
        # overlap with md_ source prefix, but exact same origin IDs -> False
        (["md_pubmed/123", "md_arxiv/999"], ["md_pubmed/123"], False),
        # overlap with md_ source prefix, different origin IDs -> True
        (["md_pubmed/123"], ["md_pubmed/456"], True),
        # mixed overlap (md_ + non-md_) -> True (falls through to final True)
        (["md_pubmed/123", "wos/0001"], ["md_pubmed/123", "wos/9999"], True),
        # overlap exists but only via md_ subset, and md_ IDs differ -> True
        (["md_pubmed/123", "scopus/0002"], ["md_pubmed/456", "wos/0001"], True),
        (
            ["CROSSREF.bib/004518", "DBLP.bib/003711", "pdfs.bib/003823"],
            ["DBLP.bib/003711"],
            False,
        ),
    ],
)
def test_same_source_merge(
    main_origins: list, dupe_origins: list, expected: bool
) -> None:
    main_record = _rec(main_origins)
    dupe_record = _rec(dupe_origins)

    result = same_source_merge(main_record=main_record, dupe_record=dupe_record)

    assert result is expected


def test_same_source_merge_requires_origin_field() -> None:
    # If your code assumes ORIGIN exists, assert that behavior explicitly
    main_record = colrev.record.record.Record(data={})
    dupe_record = _rec(["wos/0001"])

    with pytest.raises(KeyError):
        same_source_merge(main_record=main_record, dupe_record=dupe_record)
