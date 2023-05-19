#! /usr/bin/env python
"""Checker for incomplete fields."""
from __future__ import annotations

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class IncompleteFieldChecker:
    """The IncompleteFieldChecker"""

    msg = "incomplete-field"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the missing-field checks"""

        for key in ["title", "journal", "booktitle", "author"]:
            if record.data.get(key, "UNKNOWN") == "UNKNOWN":
                continue
            if self.__incomplete_field(record=record, key=key):
                record.add_masterdata_provenance_note(key=key, note=self.msg)
            else:
                record.remove_masterdata_provenance_note(key=key, note=self.msg)

    def __incomplete_field(self, *, record: colrev.record.Record, key: str) -> bool:
        """check for incomplete field"""
        if record.data[key].endswith("...") or record.data[key].endswith("…"):
            return True
        return key == "author" and (
            # heuristics for missing first names:
            ", and " in record.data[key]
            or record.data[key].rstrip().endswith(",")
            or "," not in record.data[key]
        )


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(IncompleteFieldChecker(quality_model))
