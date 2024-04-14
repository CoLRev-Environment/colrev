#! /usr/bin/env python
"""Checker for language-unknown."""
from __future__ import annotations

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class LanguageChecker:
    """The LanguageChecker"""

    msg = DefectCodes.LANGUAGE_UNKNOWN

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the language-unknown checks"""

        if record.data.get(
            Fields.TITLE, FieldValues.UNKNOWN
        ) == FieldValues.UNKNOWN or record.ignored_defect(
            key=Fields.TITLE, defect=self.msg
        ):
            return
        if record.masterdata_is_curated():
            return

        if self._language_unknown(record=record):
            record.add_field_provenance_note(key=Fields.TITLE, note=self.msg)

        else:
            record.remove_field_provenance_note(key=Fields.TITLE, note=self.msg)

    def _language_unknown(self, *, record: colrev.record.record.Record) -> bool:
        if Fields.LANGUAGE in record.data:
            return False
        return True


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(LanguageChecker(quality_model))
