#! /usr/bin/env python
"""Checker for thesis-with-multiple-authors."""
from __future__ import annotations

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class ThesisWithMultipleAuthorsChecker:
    """The ThesisWithMultipleAuthorsChecker"""

    msg = DefectCodes.THESIS_WITH_MULTIPLE_AUTHORS

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the thesis-with-multiple-authors checks"""

        if record.ignored_defect(key=Fields.AUTHOR, defect=self.msg):
            return

        if self._multiple_authored_thesis(record=record):
            record.add_field_provenance_note(key=Fields.AUTHOR, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.AUTHOR, note=self.msg)

    def _multiple_authored_thesis(self, *, record: colrev.record.record.Record) -> bool:
        if Fields.ENTRYTYPE not in record.data or Fields.AUTHOR not in record.data:
            return False
        if record.data["ENTRYTYPE"] in [
            "thesis",
            "phdthesis",
            "mastertsthesis",
        ] and " and " in record.data.get(Fields.AUTHOR, ""):
            return True
        return False


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ThesisWithMultipleAuthorsChecker(quality_model))
