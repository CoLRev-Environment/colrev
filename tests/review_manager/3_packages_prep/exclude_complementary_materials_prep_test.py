#!/usr/bin/env python
"""Test the exclude_complementary_materials prep package"""
from copy import deepcopy

import pytest

import colrev.ops.prep
import colrev.packages.exclude_complementary_materials.src.exclude_complementary_materials
from colrev.constants import Fields
from colrev.constants import RecordState

# flake8: noqa: E501

ECMPrep = (
    colrev.packages.exclude_complementary_materials.src.exclude_complementary_materials.ExcludeComplementaryMaterialsPrep
)


@pytest.fixture(scope="package", name="elp_ecm")
def elp(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> ECMPrep:
    """Fixture returning an ExcludeComplementaryMaterialsPrep instance"""
    settings = {"endpoint": "colrev.exclude_complementary_materials"}
    prep_operation = base_repo_review_manager.get_prep_operation()
    elp_instance = ECMPrep(prep_operation=prep_operation, settings=settings)
    return elp_instance


PRESCREEN_EXCLUDED = True
PRESCREEN_INCLUDED = False


@pytest.mark.parametrize(
    "input_value, expected_outcome",
    [
        (
            {
                Fields.TITLE: "About our authors",
            },
            PRESCREEN_EXCLUDED,
        ),
        (
            {
                Fields.TITLE: "Editorial board",
            },
            PRESCREEN_EXCLUDED,
        ),
        (
            {
                Fields.TITLE: "A survey of dditorial boards",
            },
            PRESCREEN_INCLUDED,
        ),
    ],
)
def test_prep_exclude_complementary_materials(
    elp_ecm: ECMPrep,
    input_value: dict,
    expected_outcome: bool,
) -> None:
    """Test the exclude_complementary_materials"""
    record = colrev.record.record_prep.PrepRecord(input_value)
    returned_record = elp_ecm.prepare(record=record)
    actual = returned_record.data
    expected = deepcopy(input_value)
    if expected_outcome == PRESCREEN_EXCLUDED:
        expected[Fields.STATUS] = RecordState.rev_prescreen_excluded
        expected[Fields.PRESCREEN_EXCLUSION] = "complementary material"

    assert expected == actual
