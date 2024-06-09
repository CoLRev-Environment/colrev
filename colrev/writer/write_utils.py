#! /usr/bin/env python
"""Convenience functions to write files (BiBTeX, RIS, CSV, etc.)

Usage::

    TODO

"""
from __future__ import annotations

from pathlib import Path

import colrev.writer.bib
import colrev.writer.csv
import colrev.writer.excel
import colrev.writer.ris


def write_file(records_dict: dict, filename: Path, **kw) -> dict:  # type: ignore
    """Write a file (BiBTex, RIS, or other) from a dictionary of records."""
    if filename.suffix == ".bib":
        writer = colrev.writer.bib.write_file  # type: ignore
    elif filename.suffix == ".ris":
        writer = colrev.writer.ris.write_file  # type: ignore
    elif filename.suffix == ".csv":
        writer = colrev.writer.csv.write_file  # type: ignore
    elif filename.suffix == ".xlsx":
        writer = colrev.writer.excel.write_file  # type: ignore
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
