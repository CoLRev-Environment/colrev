#!/usr/bin/env python
"""Test the dedupe standard package"""
from pathlib import Path

import pandas as pd
import pytest

import colrev.ops.built_in.dedupe.dedupe
import colrev.ops.dedupe


@pytest.fixture(scope="package", name="dedupe_instance")
def dedupe_standard_package(  # type: ignore
    dedupe_operation: colrev.ops.dedupe.Dedupe,
) -> colrev.ops.built_in.dedupe.dedupe.Dedupe:
    """Fixture returning an Dedupe instance"""

    settings = {"endpoint": "colrev.dedupe"}
    dedupe_instance = colrev.ops.built_in.dedupe.dedupe.Dedupe(
        dedupe_operation=dedupe_operation, settings=settings
    )
    return dedupe_instance


@pytest.fixture(scope="module", name="prepared_records")
def prepared_records(  # type: ignore
    dedupe_operation: colrev.ops.dedupe.Dedupe,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> list:
    """Fixture returning the prepared_records"""
    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="dedupe_commit"
    )

    print(Path.cwd())  # To facilitate debugging

    helpers.retrieve_test_file(
        source=Path("dedupe_package/records.bib"),
        target=Path("data/records.bib"),
    )

    records = base_repo_review_manager.dataset.load_records_dict()
    records_df = pd.DataFrame.from_dict(records, orient="index")

    records = dedupe_operation.prep_records(records_df=records_df)
    records_df = pd.DataFrame.from_dict(records, orient="index")
    return records_df


@pytest.fixture(scope="module", name="expected_blocked")
def expected_blocked(helpers) -> list:  # type: ignore
    """Fixture returning the expected blocks"""
    expected_blocked = pd.read_csv(
        helpers.test_data_path / Path("dedupe_package/expected_blocked.csv")
    )

    expected_pairs = list(
        expected_blocked["ID1"].astype(str) + "-" + expected_blocked["ID2"].astype(str)
    )
    return expected_pairs


@pytest.fixture(scope="module", name="expected_true_dupes")
def expected_true_dupes(helpers) -> list:  # type: ignore
    """Fixture returning the expected_true_dupes"""
    expected_true_dupes = pd.read_csv(
        helpers.test_data_path / Path("dedupe_package/expected_true_duplicates.csv")
    )

    expected_td_pairs = expected_true_dupes["merged_origins"].apply(eval).tolist()

    return expected_td_pairs


def test_dedupe(
    dedupe_instance: colrev.ops.built_in.dedupe.dedupe.Dedupe,
    prepared_records: pd.DataFrame,
    expected_blocked: list,
    expected_true_dupes: list,
) -> None:
    """Test the dedupe standard package"""

    # Blocking
    actual_blocked_df = dedupe_instance.block_pairs_for_deduplication(
        records_df=prepared_records
    )
    actual_blocked = list(
        actual_blocked_df["ID1"].astype(str)
        + "-"
        + actual_blocked_df["ID2"].astype(str)
    )
    for actual_item in actual_blocked:
        assert actual_item in expected_blocked
    for expected_item in expected_blocked:
        assert expected_item in actual_blocked

    results = dedupe_instance.identify_true_matches(actual_blocked_df)

    # Matching (true_dupes)
    predicted_dupes = results["duplicate_origin_sets"]

    for actual_item in predicted_dupes:
        assert actual_item in expected_true_dupes
    for expected_item in expected_true_dupes:
        assert expected_item in predicted_dupes

    # TODO : switch to origins (instead of IDs)
    # TODO : remove fields form test-records (anonymize origins)

    # TODO : maybe_pairs

    # print(true_matches)
    # raise FileNotFoundError
