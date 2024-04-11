#! /usr/bin/env python
"""Checker for no-text-in-pdf."""
from __future__ import annotations

from pathlib import Path

import colrev.env.utils
import colrev.record.qm.quality_model
from colrev.constants import Fields
from colrev.constants import PDFDefectCodes

# pylint: disable=too-few-public-methods


class TextInPDFChecker:
    """The TextInPDFChecker"""

    msg = PDFDefectCodes.NO_TEXT_IN_PDF

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the no-text-in-pdf checks"""

        if (
            Fields.FILE not in record.data
            or Path(record.data[Fields.FILE]).suffix != ".pdf"
            or record.ignored_defect(key=Fields.FILE, defect=self.msg)
        ):
            return

        if not self._text_in_pdf(record=record):
            record.add_field_provenance_note(key=Fields.FILE, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.FILE, note=self.msg)

    def _text_in_pdf(
        self,
        *,
        record: colrev.record.record.Record,
    ) -> bool:
        if record.data[Fields.TEXT_FROM_PDF] == "":
            return False

        return True


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(TextInPDFChecker(quality_model))
