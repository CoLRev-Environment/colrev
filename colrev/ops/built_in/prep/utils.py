#! /usr/bin/env python
"""Utility for prep"""
from __future__ import annotations

import re

NO_CAPS = ["of", "for", "the", "and"]
ALL_CAPS = ["IEEE", "ACM", "M&A", "B2B", "B2C", "C2C"]
ALL_CAPS_DICT = {r"U\.S\.": "U.S."}


def capitalize_entities(input_str: str) -> str:
    """Utility function to capitalize entities"""

    for all_cap in ALL_CAPS:
        input_str = re.sub(all_cap.lower(), all_cap, input_str, flags=re.IGNORECASE)

    for all_cap, repl in ALL_CAPS_DICT.items():
        input_str = re.sub(all_cap.lower(), repl, input_str, flags=re.IGNORECASE)

    for no_cap in NO_CAPS:
        input_str = re.sub(no_cap, no_cap, input_str, flags=re.IGNORECASE)

    input_str = (
        input_str.replace(" i ", " I ").replace(" i'", " I'").replace("'S ", "'s ")
    )

    input_str = re.sub(r"it-(\w)", r"IT-\1", input_str, flags=re.IGNORECASE)
    input_str = re.sub(r"is-(\w)", r"IS-\1", input_str, flags=re.IGNORECASE)

    return input_str
