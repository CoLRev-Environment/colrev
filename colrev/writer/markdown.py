#! /usr/bin/env python
"""Function to write Markdown (table) files"""
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


def to_string(
    *,
    records_dict: dict,
    sort_fields_first: bool = True,
    drop_empty_fields: bool = True,
) -> str:
    """Convert a records dict to a markdown string with a table"""
    data_frame = to_dataframe(
        records_dict=records_dict,
        sort_fields_first=sort_fields_first,
        drop_empty_fields=drop_empty_fields,
    )

    headers = list(data_frame.columns)
    md_lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for _, row in data_frame.iterrows():
        row_values = [str(row[h]).replace("\n", " ") for h in headers]
        md_lines.append("| " + " | ".join(row_values) + " |")

    return "\n".join(md_lines)


def write_file(
    *,
    records_dict: dict,
    filename: str,
    sort_fields_first: bool = True,
    drop_empty_fields: bool = True,
) -> None:
    """Write a markdown file with a table from a records dict"""
    md_string = to_string(
        records_dict=records_dict,
        sort_fields_first=sort_fields_first,
        drop_empty_fields=drop_empty_fields,
    )
    with open(filename, "w", encoding="utf-8") as f:
        f.write(md_string)
