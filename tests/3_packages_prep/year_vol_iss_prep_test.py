#!/usr/bin/env python
"""Test the year_vol_iss prep"""
import pytest

import colrev.ops.prep
import colrev.packages.get_year_from_vol_iss_jour.src.year_vol_iss_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import OperationsType


@pytest.fixture(name="yvip")
def get_yvip(
    prep_operation: colrev.ops.prep.Prep,
) -> colrev.packages.get_year_from_vol_iss_jour.src.year_vol_iss_prep.YearVolIssPrep:
    """Get the YearVolIssPrep fixture"""
    settings = {"endpoint": "colrev.exclude_languages"}
    prep_operation.review_manager.notified_next_operation = OperationsType.check
    yvip = (
        colrev.packages.get_year_from_vol_iss_jour.src.year_vol_iss_prep.YearVolIssPrep(
            prep_operation=prep_operation, settings=settings
        )
    )
    return yvip


@pytest.mark.parametrize(
    "input_rec, expected",
    [
        # Note : the first case is indexed in local_index
        (
            {
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.JOURNAL: "MIS Quarterly",
                Fields.VOLUME: "42",
                Fields.NUMBER: "2",
            },
            {
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.MD_PROV: {Fields.YEAR: {"note": "", "source": "LocalIndexPrep"}},
                Fields.D_PROV: {},
                Fields.JOURNAL: "MIS Quarterly",
                Fields.YEAR: "2018",
                Fields.VOLUME: "42",
                Fields.NUMBER: "2",
            },
        ),
        # Note : the first case requires crossref
        # (
        #     {
        #         Fields.JOURNAL: "MIS Quarterly",
        #         Fields.VOLUME: "40",
        #         Fields.NUMBER: "2",
        #     },
        #     {
        #         Fields.MD_PROV: {
        #             Fields.YEAR: {"note": "", "source": "CROSSREF(average)"}
        #         },
        #         Fields.JOURNAL: "MIS Quarterly",
        #         Fields.YEAR: "2016",
        #         Fields.VOLUME: "40",
        #         Fields.NUMBER: "2",
        #     },
        # ),
    ],
)
def test_prep_year_vol_iss(
    yvip: colrev.packages.get_year_from_vol_iss_jour.src.year_vol_iss_prep.YearVolIssPrep,
    input_rec: dict,
    expected: dict,
    prep_operation: colrev.ops.prep.Prep,
) -> None:
    """Test year_vol_iss_prep()"""
    # TODO : reactivate test
    record = colrev.record.record_prep.PrepRecord(input_rec)
    returned_record = yvip.prepare(record=record)
    actual = returned_record.data
    assert expected == actual
