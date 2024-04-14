#! /usr/bin/env python
"""Checker for name-abbreviated."""
from __future__ import annotations

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class NameAbbreviatedChecker:
    """The NameAbbreviatedChecker"""

    fields_to_check = [Fields.AUTHOR, Fields.EDITOR]
    abbreviations = ["and others", "et al", "..."]

    msg = DefectCodes.NAME_ABBREVIATED

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the name-abbreviated checks"""

        for key in self.fields_to_check:
            if key not in record.data or record.ignored_defect(
                key=key, defect=self.msg
            ):
                continue

            if record.masterdata_is_curated():
                continue

            if any(
                record.data[key].rstrip(" .").endswith(abbrev)
                for abbrev in self.abbreviations
            ):
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(NameAbbreviatedChecker(quality_model))
