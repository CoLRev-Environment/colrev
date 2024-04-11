#! /usr/bin/env python
"""Checker for language-format-error."""
from __future__ import annotations

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class LanguageFormatChecker:
    """The LanguageFormatChecker"""

    msg = DefectCodes.LANGUAGE_FORMAT_ERROR

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model
        self.language_service = colrev.env.language_service.LanguageService()

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the language-format-error checks"""

        if Fields.LANGUAGE not in record.data or record.ignored_defect(
            key=Fields.LANGUAGE, defect=self.msg
        ):
            return

        try:
            self.language_service.validate_iso_639_3_language_codes(
                lang_code_list=[record.data[Fields.LANGUAGE]]
            )
        except colrev_exceptions.InvalidLanguageCodeException:
            record.add_field_provenance_note(key=Fields.LANGUAGE, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.LANGUAGE, note=self.msg)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(LanguageFormatChecker(quality_model))
