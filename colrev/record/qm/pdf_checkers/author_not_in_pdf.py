#! /usr/bin/env python
"""Checker for author-not-in-pdf."""
from __future__ import annotations

import re
from pathlib import Path

import colrev.env.utils
import colrev.record.qm.quality_model
from colrev.constants import Fields
from colrev.constants import PDFDefectCodes

# pylint: disable=too-few-public-methods

# Note: replaces author_not_in_first_pages


class AuthorNotInPDFChecker:
    """The AuthorNotInPDFChecker"""

    msg = PDFDefectCodes.AUTHOR_NOT_IN_PDF

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the author-not-in-pdf checks"""

        if (
            Fields.FILE not in record.data
            or Path(record.data[Fields.FILE]).suffix != ".pdf"
            or Fields.AUTHOR not in record.data
            or record.data[Fields.TEXT_FROM_PDF] == ""
            or record.ignored_defect(key=Fields.FILE, defect=self.msg)
        ):
            return

        if not self._author_in_pdf(record=record):
            record.add_field_provenance_note(key=Fields.FILE, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.FILE, note=self.msg)

    def _author_in_pdf(self, *, record: colrev.record.record.Record) -> bool:
        # Many editorials do not have authors in the PDF (or on the last page)
        if "editorial" in record.data.get(Fields.TITLE, "").lower():
            return True

        text = record.data[Fields.TEXT_FROM_PDF].lower()
        text = colrev.env.utils.remove_accents(text)
        text = re.sub("[^a-zA-Z ]+", "", text)
        text = text.replace("ue", "u").replace("ae", "a").replace("oe", "o")

        authors_str = record.data.get(Fields.AUTHOR, "").lower()
        authors_str = (
            authors_str.replace("ue", "u").replace("ae", "a").replace("oe", "o")
        )
        authors_str = colrev.env.utils.remove_accents(authors_str)
        authors_str = re.sub("[^a-zA-Z, ]+", "", authors_str)

        match_count = 0
        for author_name in authors_str.split(" and "):
            # Only check last names because first names amy be abbreviated
            author_name = author_name.split(",")[0].replace(" ", "")
            if author_name in text:
                match_count += 1

        nr_authors = len(authors_str.split(" and "))
        if match_count / nr_authors > 0.8:
            return True

        return False


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(AuthorNotInPDFChecker(quality_model))
