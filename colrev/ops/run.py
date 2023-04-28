#! /usr/bin/env python3
"""CoLRev run operation: A simple tutorial version."""
from __future__ import annotations

import bibtexparser


def add_jif(*, record: dict) -> None:
    """Add the journal impact factor"""

    if record["journal"] == "MIS Quarterly":
        record["journal_impact_factor"] = 8.3
    if record["journal"] == "Information & Management":
        record["journal_impact_factor"] = 10.3


def main() -> None:
    print("Start simple colrev run")

    with open("records.bib", encoding="utf-8") as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)

    for record in bib_database.entries:
        add_jif(record=record)
        print(record)

