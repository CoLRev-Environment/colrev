#! /usr/bin/env python3
"""CoLRev run operation: A simple tutorial version."""
from __future__ import annotations


def main() -> None:
    print("Start simple colrev run")

    record = {
        "ID": "Pare2023",
        "title": "On writing literature reviews",
        "journal": "MIS Quarterly",
        "year": "2023",
        "author": "Pare, Guy",
    }

    record["colrev_status"] = "md_imported"

    print(record)
