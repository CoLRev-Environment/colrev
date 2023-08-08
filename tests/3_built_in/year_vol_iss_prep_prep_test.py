#!/usr/bin/env python
"""Test the year_vol_iss prep"""
import pytest

import colrev.ops.built_in.prep.year_vol_iss_prep
import colrev.ops.prep


@pytest.fixture(name="yvip")
def get_yvip(
    prep_operation: colrev.ops.prep.Prep,
) -> colrev.ops.built_in.prep.year_vol_iss_prep.YearVolIssPrep:
    """Get the YearVolIssPrep fixture"""
    settings = {"endpoint": "colrev.exclude_languages"}
    yvip = colrev.ops.built_in.prep.year_vol_iss_prep.YearVolIssPrep(
        prep_operation=prep_operation, settings=settings
    )
    return yvip


@pytest.mark.parametrize(
    "input_rec, expected",
    [
        # Note : the first case is indexed in local_index
        (
            {
                "ENTRYTYPE": "article",
                "journal": "MIS Quarterly",
                "volume": "42",
                "number": "2",
            },
            {
                "ENTRYTYPE": "article",
                "colrev_masterdata_provenance": {
                    "year": {"note": "", "source": "LocalIndexPrep"}
                },
                "journal": "MIS Quarterly",
                "year": "2018",
                "volume": "42",
                "number": "2",
            },
        ),
        # Note : the first case requires crossref
        (
            {
                "journal": "MIS Quarterly",
                "volume": "40",
                "number": "2",
            },
            {
                "colrev_masterdata_provenance": {
                    "year": {"note": "", "source": "CROSSREF(average)"}
                },
                "journal": "MIS Quarterly",
                "year": "2016",
                "volume": "40",
                "number": "2",
            },
        ),
    ],
)
def test_prep_year_vol_iss(
    yvip: colrev.ops.built_in.prep.year_vol_iss_prep.YearVolIssPrep,
    input_rec: dict,
    expected: dict,
    prep_operation: colrev.ops.prep.Prep,
) -> None:
    """Test year_vol_iss_prep()"""
    # TODO : reactivate test
    # record = colrev.record.PrepRecord(data=input_rec)
    # returned_record = yvip.prepare(prep_operation=prep_operation, record=record)
    # actual = returned_record.data
    # assert expected == actual
