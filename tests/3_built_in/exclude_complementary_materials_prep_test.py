#!/usr/bin/env python
"""Test the exclude_complementary_materials prep package"""
from copy import deepcopy

import pytest

import colrev.ops.built_in.prep.exclude_complementary_materials
import colrev.ops.prep
from colrev.constants import Fields
from colrev.constants import RecordState

ECMPrep = (
    colrev.ops.built_in.prep.exclude_complementary_materials.ExcludeComplementaryMaterialsPrep
)


@pytest.fixture(scope="package", name="elp_ecm")
def elp(
    prep_operation: colrev.ops.prep.Prep,
) -> ECMPrep:
    """Fixture returning an ExcludeComplementaryMaterialsPrep instance"""
    settings = {"endpoint": "colrev.exclude_complementary_materials"}
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
    record = colrev.record_prep.PrepRecord(data=input_value)
    returned_record = elp_ecm.prepare(record=record)
    actual = returned_record.data
    expected = deepcopy(input_value)
    if expected_outcome == PRESCREEN_EXCLUDED:
        expected[Fields.STATUS] = RecordState.rev_prescreen_excluded
        expected[Fields.PRESCREEN_EXCLUSION] = "complementary material"

    assert expected == actual
