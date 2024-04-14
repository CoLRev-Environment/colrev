#! /usr/bin/env python
"""Checker for inconsistent-content."""
from __future__ import annotations

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class InconsistentContentChecker:
    """The InconsistentContentChecker"""

    msg = DefectCodes.INCONSISTENT_CONTENT

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the inconsistent-content checks"""

        for key in [Fields.JOURNAL, Fields.BOOKTITLE, Fields.AUTHOR]:
            if key not in record.data or record.ignored_defect(
                key=key, defect=self.msg
            ):
                continue

            if record.masterdata_is_curated():
                continue

            if self._inconsistent_content(record=record, key=key):
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)

    def _inconsistent_content(
        self, *, record: colrev.record.record.Record, key: str
    ) -> bool:
        if key == Fields.JOURNAL:
            if Fields.JOURNAL in record.data and any(
                x in record.data[Fields.JOURNAL].lower()
                for x in ["conference", "workshop"]
            ):
                return True
        if key == Fields.BOOKTITLE:
            if Fields.BOOKTITLE in record.data and any(
                x in record.data[Fields.BOOKTITLE].lower() for x in [Fields.JOURNAL]
            ):
                return True

        return False


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(InconsistentContentChecker(quality_model))
