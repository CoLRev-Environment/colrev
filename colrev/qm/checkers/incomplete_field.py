#! /usr/bin/env python
"""Checker for incomplete fields."""
from __future__ import annotations

import colrev.qm.quality_model
import colrev.record

# pylint: disable=too-few-public-methods


class IncompleteFieldChecker:
    """The IncompleteFieldChecker"""

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the missing-field checks"""

        for key in ["title", "journal", "booktitle", "author"]:
            if key not in record.data:
                continue
            if self.__incomplete_field(record=record, key=key):
                record.add_masterdata_provenance_note(key=key, note="incomplete-field")
            else:
                record.remove_masterdata_provenance_note(
                    key=key, note="incomplete-field"
                )

    def __incomplete_field(self, *, record: colrev.record.Record, key: str) -> bool:
        if key in ["title", "journal", "booktitle", "author"]:
            if record.data[key].endswith("...") or record.data[key].endswith("…"):
                return True
        if key == "author":
            if (
                record.data[key].endswith("and others")
                or record.data[key].endswith("et al.")
                # heuristics for missing first names:
                or ", and " in record.data[key]
                or record.data[key].rstrip().endswith(",")
            ):
                return True
        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(IncompleteFieldChecker(quality_model))
