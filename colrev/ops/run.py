#! /usr/bin/env python3
"""CoLRev run operation: A simple tutorial version."""
from __future__ import annotations

import colrev.review_manager


class JIFLabeler:
    """Object handling the JIF labeling"""

    def __init__(self) -> None:
        self.review_manager = colrev.review_manager.ReviewManager()

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

        self.review_manager.get_prep_operation()
        records = self.review_manager.dataset.load_records_dict()

        for record in records.values():
            self.add_jif(record=record)
            print(record)

def main() -> None:
    jif_labeler = JIFLabeler()
    jif_labeler.run()
