#!/usr/bin/env python
"""Test the colrev_id"""
import pytest

import colrev.qm.colrev_id
import colrev.record
import colrev.review_manager

# pylint: disable=line-too-long

@pytest.mark.parametrize(
    "record_dict, colrev_id",
    [
        (
            {
                "ENTRYTYPE": "article",
                "ID": "Staehr2010",
                "author": "Staehr, Lorraine",
                "journal": "Information Systems Journal",
                "title": "Understanding the role of managerial agency in achieving business benefits from ERP systems",
                "year": "2010",
                "volume": "20",
                "number": "3",
                "pages": "213--238",
            },
            "colrev_id1:|a|information-systems-journal|20|3|2010|staehr|understanding-the-role-of-managerial-agency-in-achieving-business-benefits-from-erp-systems",
        )
    ],
)
def test_pdf_hash(  # type: ignore
    record_dict: dict,
    colrev_id: str,
) -> None:
    """Test the colrev_id generation"""

    actual = colrev.qm.colrev_id.create_colrev_id(
        record=colrev.record.Record(data=record_dict),
        assume_complete=True,
    )
    assert actual == colrev_id
