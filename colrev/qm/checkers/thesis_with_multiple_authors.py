#! /usr/bin/env python
"""Checker for thesis-with-multiple-authors."""
from __future__ import annotations

import colrev.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class ThesisWithMultipleAuthorsChecker:
    """The ThesisWithMultipleAuthorsChecker"""

    msg = DefectCodes.THESIS_WITH_MULTIPLE_AUTHORS

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the thesis-with-multiple-authors checks"""

        if self.__multiple_authored_thesis(record=record):
            record.add_masterdata_provenance_note(key=Fields.AUTHOR, note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key=Fields.AUTHOR, note=self.msg)

    def __multiple_authored_thesis(self, *, record: colrev.record.Record) -> bool:
        if record.data["ENTRYTYPE"] in [
            "thesis",
            "phdthesis",
            "mastertsthesis",
        ] and " and " in record.data.get(Fields.AUTHOR, ""):
            return True
        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ThesisWithMultipleAuthorsChecker(quality_model))
