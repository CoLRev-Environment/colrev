#! /usr/bin/env python3
"""CoLRev run operation: A simple tutorial version."""
from __future__ import annotations

import bibtexparser


class JIFLabeler:
    """Object handling the JIF labeling"""

    def __init__(self) -> None:
        pass

    def add_jif(self, *, record: dict) -> None:
        """Add the journal impact factor"""
        if "journal" not in record:
            return

        if record["journal"] == "MIS Quarterly":
            record["journal_impact_factor"] = 8.3
        if record["journal"] == "Information & Management":
            record["journal_impact_factor"] = 10.3

    def run(self) -> None:
        print("Start simple colrev run")

        with open("data/records.bib", encoding="utf-8") as bibtex_file:
            bib_database = bibtexparser.load(bibtex_file)

        for record in bib_database.entries:
            self.add_jif(record=record)
            print(record)

def main() -> None:
    jif_labeler = JIFLabeler()
    jif_labeler.run()
