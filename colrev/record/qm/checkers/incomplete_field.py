#! /usr/bin/env python
"""Checker for incomplete fields."""
from __future__ import annotations

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class IncompleteFieldChecker:
    """The IncompleteFieldChecker"""

    msg = DefectCodes.INCOMPLETE_FIELD

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the missing-field checks"""

        for key in [
            Fields.TITLE,
            Fields.JOURNAL,
            Fields.BOOKTITLE,
            Fields.AUTHOR,
            Fields.ABSTRACT,
        ]:
            if (
                self._institutional_author(key=key, record=record)
                or record.data.get(key, FieldValues.UNKNOWN) == FieldValues.UNKNOWN
                or record.ignored_defect(key=key, defect=self.msg)
            ):
                record.remove_field_provenance_note(key=key, note=self.msg)
                continue

            if record.masterdata_is_curated():
                continue

            if self._incomplete_field(record=record, key=key):
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)

    def _incomplete_field(
        self, *, record: colrev.record.record.Record, key: str
    ) -> bool:
        """Check for incomplete field."""
        if record.data[key].endswith("...") or record.data[key].endswith("…"):
            return True
        if key == Fields.AUTHOR:
            if (
                # heuristics for missing first names:
                ", and " in record.data[key]
                or record.data[key].rstrip().endswith(",")
                or "," not in record.data[key]
            ):
                return True
        return False

    def _institutional_author(
        self, *, key: str, record: colrev.record.record.Record
    ) -> bool:
        if key != Fields.AUTHOR or Fields.AUTHOR not in record.data:
            return False
        if record.data[Fields.AUTHOR].startswith("{") and record.data[
            Fields.AUTHOR
        ].endswith("}"):
            return True
        return False


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(IncompleteFieldChecker(quality_model))
