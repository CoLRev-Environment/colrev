#! /usr/bin/env python
"""Checker for title-not-in-pdf."""
from __future__ import annotations

import re
from pathlib import Path

import colrev.env.utils
import colrev.record.qm.quality_model
from colrev.constants import Fields
from colrev.constants import PDFDefectCodes

# pylint: disable=too-few-public-methods

# Note: replaces title_not_in_first_pages


class TitleNotInPDFChecker:
    """The TitleNotInPDFChecker"""

    msg = PDFDefectCodes.TITLE_NOT_IN_PDF

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the title-not-in-pdf checks"""

        if (
            Fields.FILE not in record.data
            or Path(record.data[Fields.FILE]).suffix != ".pdf"
            or Fields.TITLE not in record.data
            or record.data[Fields.TEXT_FROM_PDF] == ""
            or record.ignored_defect(key=Fields.FILE, defect=self.msg)
        ):
            return

        if not self._title_in_pdf(record=record):
            record.add_field_provenance_note(key=Fields.FILE, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.FILE, note=self.msg)

    def _title_in_pdf(self, *, record: colrev.record.record.Record) -> bool:
        text = record.data[Fields.TEXT_FROM_PDF]
        text = text.replace(" ", "").replace("\n", "").lower()
        text = colrev.env.utils.remove_accents(text)
        text = re.sub("[^a-zA-Z ]+", "", text)

        title_words = (
            re.sub("[^a-zA-Z ]+", "", record.data[Fields.TITLE]).lower().split()
        )

        match_count = 0
        for title_word in title_words:
            if title_word in text:
                match_count += 1

        if match_count / len(title_words) > 0.9:
            return True

        return False


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(TitleNotInPDFChecker(quality_model))
