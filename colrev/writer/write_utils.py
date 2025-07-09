#! /usr/bin/env python
"""Function to write files (BiBTeX, RIS, CSV, etc.)

Usage::

    import colrev.loader.load_utils
    import colrev.writer.write_utils

    # Load
    records = colrev.loader.load_utils.load(filename=filename)

    # Write
    colrev.writer.write_utils.write_file(records, filename=filename)

"""
from __future__ import annotations

from pathlib import Path

import colrev.writer.bib
import colrev.writer.csv
import colrev.writer.excel
import colrev.writer.markdown
import colrev.writer.ris


def write_file(records_dict: dict, *, filename: Path, **kw) -> dict:  # type: ignore
    """Write a file (BiBTex, RIS, or other) from a dictionary of records.

    Note:
        For tabular formats (csv, xlsx, md), the following options are supported:
            - sort_fields_first: list of fields to appear first in the output
            - drop_empty_fields: if True, empty fields will be omitted
    """
    if isinstance(filename, str):
        filename = Path(filename)
    if filename.suffix == ".bib":
        writer = colrev.writer.bib.write_file  # type: ignore
    elif filename.suffix == ".ris":
        writer = colrev.writer.ris.write_file  # type: ignore
    elif filename.suffix == ".csv":
        writer = colrev.writer.csv.write_file  # type: ignore
    elif filename.suffix == ".xlsx":
        writer = colrev.writer.excel.write_file  # type: ignore
    elif filename.suffix == ".md":
        writer = colrev.writer.markdown.write_file  # type: ignore
    else:
        raise NotImplementedError

    kw["filename"] = filename
    kw["records_dict"] = records_dict

    writer(**kw)


def to_string(*, records_dict: dict, implementation: str, **kw) -> str:  # type: ignore
    """Write a string (BiBTex, RIS, or other) from a dictionary of records."""
    if implementation == "bib":
        writer = colrev.writer.bib.to_string  # type: ignore
    elif implementation == "ris":
        writer = colrev.writer.ris.to_string  # type: ignore
    else:
        raise NotImplementedError

    kw["records_dict"] = records_dict

    return writer(**kw)


# see https://github.com/MrTango/rispy/blob/main/rispy/parser.py
