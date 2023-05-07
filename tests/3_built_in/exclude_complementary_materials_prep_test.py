#!/usr/bin/env python
"""Test the exclude_complementary_materials prep package"""
from copy import deepcopy

import pytest

import colrev.ops.built_in.prep.exclude_complementary_materials
import colrev.ops.prep


@pytest.fixture(scope="package")
def elp(
    prep_operation: colrev.ops.prep.Prep,
) -> (
    colrev.ops.built_in.prep.exclude_complementary_materials.ExcludeComplementaryMaterialsPrep
):
    """Fixture returning an ExcludeComplementaryMaterialsPrep instance"""
    settings = {"endpoint": "colrev.exclude_complementary_materials"}
    elp_instance = colrev.ops.built_in.prep.exclude_complementary_materials.ExcludeComplementaryMaterialsPrep(
        prep_operation=prep_operation, settings=settings
    )
    return elp_instance


PRESCREEN_EXCLUDED = True
PRESCREEN_INCLUDED = False


@pytest.mark.parametrize(
    "input_value, expected_outcome",
    [
        (
            {
                "title": "About our authors",
            },
            PRESCREEN_EXCLUDED,
        ),
        (
            {
                "title": "Editorial board",
            },
            PRESCREEN_EXCLUDED,
        ),
        (
            {
                "title": "A survey of dditorial boards",
            },
            PRESCREEN_INCLUDED,
        ),
    ],
)
def test_prep_exclude_complementary_materials(
    elp: colrev.ops.built_in.prep.exclude_complementary_materials.ExcludeComplementaryMaterialsPrep,
    input_value: dict,
    expected_outcome: bool,
) -> None:
    """Test the exclude_complementary_materials"""
    record = colrev.record.PrepRecord(data=input_value)
    returned_record = elp.prepare(prep_operation=elp, record=record)
    actual = returned_record.data
    expected = deepcopy(input_value)
    if expected_outcome == PRESCREEN_EXCLUDED:
        expected["colrev_status"] = colrev.record.RecordState.rev_prescreen_excluded
        expected["prescreen_exclusion"] = "complementary material"

    assert expected == actual
