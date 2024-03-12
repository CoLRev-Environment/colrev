#! /usr/bin/env python
"""Convenience functions to write files (BiBTeX, RIS, CSV, etc.)

Usage::

    TODO

"""
from __future__ import annotations

from pathlib import Path

import colrev.writer.bib


def write_file(records_dict: dict, filename: Path, **kw) -> dict:  # type: ignore
    """Write a file (BiBTex, RIS, or other) from a dictionary of records."""
    if filename.suffix == ".bib":
        writer = colrev.writer.bib.write_file  # type: ignore

    kw["filename"] = filename
    kw["records_dict"] = records_dict

    writer(**kw)


def to_string(*, records_dict: dict, implementation: str, **kw) -> str:  # type: ignore
    """Write a string (BiBTex, RIS, or other) from a dictionary of records."""
    if implementation == "bib":
        writer = colrev.writer.bib.to_string  # type: ignore

    kw["records_dict"] = records_dict

    return writer(**kw)


# see https://github.com/MrTango/rispy/blob/main/rispy/parser.py
