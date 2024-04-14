#! /usr/bin/env python
"""Checker for year-format."""
from __future__ import annotations

import re

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class YearFormatChecker:
    """The YearFormatChecker"""

    msg = DefectCodes.YEAR_FORMAT

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the year-format checks"""

        if (
            Fields.YEAR not in record.data
            or record.ignored_defect(key=Fields.YEAR, defect=self.msg)
            or record.data[Fields.YEAR] == FieldValues.UNKNOWN
        ):
            return

        if record.masterdata_is_curated():
            return

        if not re.match(r"^\d{4}$", record.data[Fields.YEAR]):
            record.add_field_provenance_note(key=Fields.YEAR, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.YEAR, note=self.msg)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(YearFormatChecker(quality_model))
