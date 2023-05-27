#! /usr/bin/env python
"""Utility for prep"""
from __future__ import annotations

import re

NO_CAPS = ["of", "for", "the", "and"]
ALL_CAPS = ["IEEE", "ACM", "M&A", "B2B", "B2C", "C2C", "U.S."]


def capitalize_entities(input_str: str) -> str:
    for ALL_CAP in ALL_CAPS:
        input_str = re.sub(ALL_CAP.lower(), ALL_CAP, input_str, flags=re.IGNORECASE)

    for NO_CAP in NO_CAPS:
        input_str = re.sub(NO_CAP, NO_CAP, input_str, flags=re.IGNORECASE)

    input_str = (
        input_str.replace(" i ", " I ").replace(" i'", " I'").replace("'S ", "'s ")
    )

    input_str = re.sub(r"it-(\w)", r"IT-\1", input_str, flags=re.IGNORECASE)
    input_str = re.sub(r"is-(\w)", r"IS-\1", input_str, flags=re.IGNORECASE)

    return input_str


if __name__ == "__main__":
    pass
