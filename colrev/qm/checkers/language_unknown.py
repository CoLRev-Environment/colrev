#! /usr/bin/env python
"""Checker for language-unknown."""
from __future__ import annotations

import colrev.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class LanguageChecker:
    """The LanguageChecker"""

    msg = DefectCodes.LANGUAGE_UNKNOWN

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the language-unknown checks"""

        if record.data.get(Fields.TITLE, FieldValues.UNKNOWN) == FieldValues.UNKNOWN:
            return

        if self.__language_unknown(record=record):
            record.add_masterdata_provenance_note(key=Fields.TITLE, note=self.msg)

        else:
            record.remove_masterdata_provenance_note(key=Fields.TITLE, note=self.msg)

    def __language_unknown(self, *, record: colrev.record.Record) -> bool:
        if Fields.LANGUAGE in record.data:
            return False
        return True


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(LanguageChecker(quality_model))
