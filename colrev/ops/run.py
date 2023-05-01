#! /usr/bin/env python3
"""CoLRev run operation: A simple tutorial version."""
from __future__ import annotations

import colrev.record
import colrev.review_manager


class JIFLabeler:
    """Object handling the JIF labeling"""

    def __init__(self) -> None:
        self.review_manager = colrev.review_manager.ReviewManager()

    def add_jif(self, *, record: colrev.record.Record) -> None:
        """Add the journal impact factor"""
        if "journal" not in record.data:
            return

        if record.data["journal"] == "MIS Quarterly":
            record.update_field(
                key="journal_impact_factor", value="8.3", source="jif-labeler"
            )
        if record.data["journal"] == "Information & Management":
            record.update_field(
                key="journal_impact_factor", value="10.3", source="jif-labeler"
            )

    def run(self) -> None:
        self.review_manager.logger.info("Start simple colrev run")

        self.review_manager.get_prep_operation()
        records = self.review_manager.dataset.load_records_dict()

        for record_dict in records.values():
            record = colrev.record.Record(data=record_dict)
            self.add_jif(record=record)
            if "journal_impact_factor" in record.data:
                self.review_manager.logger.info(record.data["ID"])

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(msg="Add JIF")


def main() -> None:
    jif_labeler = JIFLabeler()
    jif_labeler.run()
