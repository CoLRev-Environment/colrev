#! /usr/bin/env python
"""Checker for fields that are inconsistent with the ENTRYTYPE."""
from __future__ import annotations

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class InconsistentWithEntrytypeChecker:
    """The InconsistentWithEntrytypeChecker"""

    record_field_inconsistencies: dict[str, list[str]] = {
        "article": ["booktitle", "isbn"],
        "inproceedings": ["issue", "number", "journal", "isbn"],
        "incollection": [],
        "inbook": ["journal"],
        "book": ["issue", "number", "journal"],
        "phdthesis": ["volume", "issue", "number", "journal", "booktitle", "isbn"],
        "masterthesis": ["volume", "issue", "number", "journal", "booktitle", "isbn"],
        "techreport": ["volume", "issue", "number", "journal", "booktitle", "isbn"],
        "unpublished": ["volume", "issue", "number", "journal", "booktitle", "isbn"],
        "online": ["journal", "booktitle", "isbn"],
        "misc": ["journal", "booktitle", "isbn"],
    }
    """Fields considered inconsistent with the respective ENTRYTYPE"""

    msg = "inconsistent-with-entrytype"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the completeness checks"""

        if record.data["ENTRYTYPE"] not in self.record_field_inconsistencies:
            return

        inconsistent_fields = self.record_field_inconsistencies[
            record.data["ENTRYTYPE"]
        ]
        for key in record.data:
            if key in inconsistent_fields:
                record.add_masterdata_provenance_note(key=key, note=self.msg)
            else:
                record.remove_masterdata_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(InconsistentWithEntrytypeChecker(quality_model))
