#! /usr/bin/env python
"""Convenience functions to write csv files"""
from __future__ import annotations

import pandas as pd

from colrev.constants import Fields

FIELDS = [
    Fields.ID,
    Fields.ENTRYTYPE,
    Fields.TITLE,
    Fields.AUTHOR,
    Fields.YEAR,
    Fields.JOURNAL,
    Fields.BOOKTITLE,
    Fields.VOLUME,
    Fields.NUMBER,
    Fields.PAGES,
    Fields.DOI,
    Fields.URL,
    Fields.FILE,
]


def to_dataframe(*, records_dict: dict) -> pd.DataFrame:
    """Convert a records dict to a pandas DataFrame"""
    data = []
    for record_id in sorted(records_dict.keys()):
        record_dict = records_dict[record_id]
        row = {}
        for field in FIELDS:
            if field in record_dict:
                row[field] = record_dict[field]
            else:
                row[field] = ""
        data.append(row)
    return pd.DataFrame(data)


def write_file(*, records_dict: dict, filename: str) -> None:
    """Write a csv file from a records dict"""
    df = to_dataframe(records_dict=records_dict)
    df.to_csv(filename, index=False)
