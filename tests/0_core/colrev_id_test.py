#!/usr/bin/env python
"""Test the colrev_id"""
import pytest

import colrev.exceptions as colrev_exceptions
import colrev.qm.colrev_id
import colrev.record
import colrev.review_manager

# pylint: disable=line-too-long
# flake8: noqa


@pytest.mark.parametrize(
    "record_dict, colrev_id",
    [
        (
            {
                "ENTRYTYPE": "article",
                "ID": "Staehr2010",
                "author": 'Staehr, Lorraine "Emma"',
                "journal": "Information Systems Journal",
                "title": "Understanding the role of managerial agency in achieving business benefits from ERP systems",
                "year": "2010",
                "volume": "20",
                "number": "3",
                "pages": "213--238",
            },
            "colrev_id1:|a|information-systems-journal|20|3|2010|staehr|understanding-the-role-of-managerial-agency-in-achieving-business-benefits-from-erp-systems",
        ),
        (
            {
                "ENTRYTYPE": "article",
                "ID": "WebsterWatson2002",
                "author": "Webster, and Watson,",
                "journal": "MIS Quarterly",
                "title": "Analyzing the past to prepare for the future: Writing a literature review",
                "year": "2002",
                "volume": "26",
                "number": "2",
                "pages": "13--23",
            },
            "colrev_id1:|a|mis-quarterly|26|2|2002|webster-watson|analyzing-the-past-to-prepare-for-the-future-writing-a-literature-review",
        ),
        (
            {
                "ENTRYTYPE": "article",
                "ID": "WebsterWatson2002",
                "author": "UNKNOWN",
                "journal": "MIS Quarterly",
                "title": "Analyzing the past to prepare for the future: Writing a literature review",
                "year": "2002",
                "volume": "26",
                "number": "2",
                "pages": "13--23",
            },
            "NotEnoughDataToIdentifyException",
        ),
        (
            {
                "ENTRYTYPE": "inproceedings",
                "ID": "Smith2002",
                "author": "Smith, Tom",
                "booktitle": "HICSS",
                "title": "Minitrack introduction",
                "year": "2002",
            },
            "NotEnoughDataToIdentifyException",
        ),
        (
            {
                "ENTRYTYPE": "article",
                "ID": "WebsterWatson2002",
                "author": "",
                "journal": "MIS Quarterly",
                "title": "Analyzing the past to prepare for the future: Writing a literature review",
                "year": "2002",
                "volume": "26",
                "number": "2",
                "pages": "13--23",
            },
            "NotEnoughDataToIdentifyException",
        ),
    ],
)
def test_colrev_id(  # type: ignore
    record_dict: dict,
    colrev_id: str,
) -> None:
    """Test the colrev_id generation"""

    if colrev_id == "NotEnoughDataToIdentifyException":
        with pytest.raises(colrev_exceptions.NotEnoughDataToIdentifyException):
            colrev.qm.colrev_id.create_colrev_id(
                record=colrev.record.Record(record_dict),
                assume_complete=False,
            )
        return

    actual = colrev.qm.colrev_id.create_colrev_id(
        record=colrev.record.Record(record_dict),
        assume_complete=False,
    )
    assert actual == colrev_id
