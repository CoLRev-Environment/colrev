#! /usr/bin/env python
"""Convenience functions to load files (BiBTeX, RIS, CSV, etc.)

Usage::

    import colrev.ops.load_utils

    # Files
    records = colrev.ops.load_utils.load(filename=filename, logger=logger)

    # Strings
    records = colrev.ops.load_utils.loads(load_str=load_str, logger=logger)

    returns: records (dict)

"""
from __future__ import annotations

import tempfile
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.record


def load(filename: Path, **kw) -> dict:  # type: ignore
    """Load a file and return records as a dictionary"""

    if not filename.exists():
        raise colrev_exceptions.ImportException(f"File not found: {filename.name}")

    # TODO : remove from load_utils_bib BIBLoader constructor (and others):
    # if not filename.exists(): -> covered in load()
    # also remove if not filename.name.endswith(".bib"): -> covered in load()

    if filename.suffix == ".bib":
        parser = colrev.ops.load_utils_bib.load_bib
    else:
        raise NotImplementedError

    kw["filename"] = filename
    return parser(**kw)


def loads(load_string: str, *, implementation: str, **kw) -> dict:  # type: ignore
    """Load a string and return records as a dictionary"""

    if implementation == "bib":
        parser = colrev.ops.load_utils_bib.load_bib
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, suffix=".bib"
        ) as temp_file:
            temp_file.write(load_string.encode("utf-8"))
            temp_file_path = Path(temp_file.name)

        kw["filename"] = temp_file_path
    else:
        raise NotImplementedError

    return parser(**kw)
