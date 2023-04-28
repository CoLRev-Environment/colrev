#! /usr/bin/env python3
"""CoLRev run operation: A simple tutorial version."""
from __future__ import annotations

import bibtexparser


def main() -> None:
    print("Start simple colrev run")

    with open("records.bib", encoding="utf-8") as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)

    for record in bib_database.entries:
        print(record["title"])
