#! /usr/bin/env python
"""Function to write Excel files with flexible field handling"""
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


def to_dataframe(
    *,
    records_dict: dict,
    sort_fields_first: bool = True,
    drop_empty_fields: bool = True,
) -> pd.DataFrame:
    """Convert a records dict to a pandas DataFrame"""
    all_keys = {k for v in records_dict.values() for k in v.keys()}
    additional_fields = sorted(all_keys - set(FIELDS))
    fields = FIELDS + additional_fields if sort_fields_first else sorted(all_keys)

    data = []
    for record_id in sorted(records_dict.keys()):
        record_dict = records_dict[record_id]
        row = {field: record_dict.get(field, "") for field in fields}
        data.append(row)

    df = pd.DataFrame(data)

    if drop_empty_fields:
        df = df.dropna(axis=1, how="all")
        df = df.loc[:, (df != "").any(axis=0)]

    return df


def write_file(
    *,
    records_dict: dict,
    filename: str,
    sort_fields_first: bool = True,
    drop_empty_fields: bool = True,
) -> None:
    """Write an Excel file from a records dict"""
    data_frame = to_dataframe(
        records_dict=records_dict,
        sort_fields_first=sort_fields_first,
        drop_empty_fields=drop_empty_fields,
    )
    writer = pd.ExcelWriter(filename, engine="xlsxwriter")
    data_frame.to_excel(writer, index=False)

    worksheet = writer.sheets["Sheet1"]
    for i, column in enumerate(data_frame.columns):
        column_width = max(data_frame[column].astype(str).map(len).max(), len(column))
        column_width = max(min(column_width, 130), 10)
        worksheet.set_column(i, i, column_width)

    writer.close()
