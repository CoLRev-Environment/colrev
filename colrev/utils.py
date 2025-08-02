#! /usr/bin/env python3
"""Utility helpers for CoLRev."""
from __future__ import annotations

import pprint
import typing

_p_printer = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def pformat(obj: typing.Any) -> str:
    """Return a pretty-formatted representation of ``obj``."""
    return _p_printer.pformat(obj)


def pprint(obj: typing.Any) -> None:
    """Pretty-print ``obj`` using repository defaults."""
    _p_printer.pprint(obj)
