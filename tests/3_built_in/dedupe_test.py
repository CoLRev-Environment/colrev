#!/usr/bin/env python
"""Test the dedupe standard package"""
from pathlib import Path

import pytest

import colrev.ops.built_in.dedupe.dedupe
import colrev.ops.dedupe
from colrev.ops.dedupe_benchmark import DedupeBenchmarker


def dedupe_dataset(
    dir, dedupe_instance: colrev.ops.built_in.dedupe.dedupe.Dedupe, helpers
) -> None:
    dedupe_benchmark = DedupeBenchmarker(
        #
        # benchmark_path=helpers.test_data_path / Path("dedupe_package"),
        benchmark_path=dir,
        colrev_project_path=Path.cwd(),
        regenerate_benchmark_from_history=False,
    )

    # Blocking
    actual_blocked_df = dedupe_instance.block_pairs_for_deduplication(
        records_df=dedupe_benchmark.get_records_for_dedupe()
    )
    matches = dedupe_instance.identify_true_matches(actual_blocked_df)

    results = dedupe_benchmark.compare(
        predicted=matches["duplicate_origin_sets"], blocked_df=actual_blocked_df
    )

    assert results["matches"]["FP"] == 0

    # TODO : switch to origins (instead of IDs)
    # TODO : remove fields form test-records (anonymize origins)

    # TODO : maybe_pairs

    # print(true_matches)
    # raise FileNotFoundError


@pytest.mark.slow
def test_dedupe(dedupe_operation: colrev.ops.dedupe.Dedupe, helpers) -> None:
    """Test the dedupe standard package"""

    settings = {"endpoint": "colrev.dedupe"}
    dedupe_instance = colrev.ops.built_in.dedupe.dedupe.Dedupe(
        dedupe_operation=dedupe_operation, settings=settings
    )

    # Workaround because parameterize happens before fixtures are available
    for dir in [
        str(d)
        for d in (helpers.test_data_path / "dedupe_package").iterdir()
        if d.is_dir()
    ]:
        dedupe_dataset(dir, dedupe_instance, helpers)
