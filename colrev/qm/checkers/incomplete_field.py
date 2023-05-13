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
        for incomplete_field in self.__get_incomplete_fields(record=record):
            record.add_masterdata_provenance_note(
                key=incomplete_field, note="incomplete-field"
            )

    def __get_incomplete_fields(self, *, record: colrev.record.Record) -> set:
        """Get the list of incomplete fields"""
        incomplete_field_keys = set()
        for key in record.data.keys():
            if key in ["title", "journal", "booktitle", "author"]:
                if record.data[key].endswith("...") or record.data[key].endswith("…"):
                    incomplete_field_keys.add(key)

            if key == "author":
                if (
                    record.data[key].endswith("and others")
                    or record.data[key].endswith("et al.")
                    # heuristics for missing first names:
                    or ", and " in record.data[key]
                    or record.data[key].rstrip().endswith(",")
                ):
                    incomplete_field_keys.add(key)

        return incomplete_field_keys


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(IncompleteFieldChecker(quality_model))
