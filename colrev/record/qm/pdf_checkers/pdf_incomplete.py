#! /usr/bin/env python
"""Checker for pdf-incomplete."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import colrev.env.utils
import colrev.record.qm.quality_model
from colrev.constants import Fields
from colrev.constants import PDFDefectCodes

# pylint: disable=too-few-public-methods

FULL_VERSION_PURCHASE_NOTICES = [
    "morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas"
]
ROMAN_PAGES_PATTERN = re.compile(
    r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?--"
    + r"M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$",
    re.IGNORECASE,
)
ROMAN_PAGE_PATTERN = re.compile(
    r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$", re.IGNORECASE
)


class PDFIncompletenessChecker:
    """The PDFIncompletenessChecker."""

    msg = PDFDefectCodes.PDF_INCOMPLETE

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        """Initialize the instance."""
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record_pdf.PDFRecord) -> None:
        """Run the pdf-incomplete checks."""
        if (
            Fields.FILE not in record.data
            or Path(record.data[Fields.FILE]).suffix != ".pdf"
            or Fields.PAGES not in record.data
            or record.ignored_defect(key=Fields.FILE, defect=self.msg)
        ):
            return

        if not self._pages_match_pdf(record=record):
            record.add_field_provenance_note(key=Fields.FILE, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.FILE, note=self.msg)

    def _pages_match_pdf(self, *, record: colrev.record.record_pdf.PDFRecord) -> bool:
        nr_pages_in_file = self._get_pdf_page_count(record=record)
        if nr_pages_in_file is None:
            return False

        if self._contains_full_version_purchase_notice(record=record):
            return False

        expected_page_count = self._get_expected_page_count(record=record)
        if expected_page_count is None:
            return True

        if self._longer_with_appendix(
            record=record,
            nr_pages=expected_page_count,
            nr_pages_in_file=nr_pages_in_file,
        ):
            return True

        return expected_page_count == nr_pages_in_file

    def _get_pdf_page_count(
        self, *, record: colrev.record.record_pdf.PDFRecord
    ) -> Optional[int]:
        if Fields.NR_PAGES_IN_FILE not in record.data:
            return None
        return record.data[Fields.NR_PAGES_IN_FILE]

    def _contains_full_version_purchase_notice(
        self, *, record: colrev.record.record_pdf.PDFRecord
    ) -> bool:
        return any(
            full_version_purchase_notice
            in record.data[Fields.TEXT_FROM_PDF].lower().replace(" ", "")
            for full_version_purchase_notice in FULL_VERSION_PURCHASE_NOTICES
        )

    def _longer_with_appendix(
        self,
        *,
        record: colrev.record.record_pdf.PDFRecord,
        nr_pages: int,
        nr_pages_in_file: int,
    ) -> bool:
        if 10 < nr_pages < nr_pages_in_file:
            text = record.extract_text_by_page(
                pages=list(range(nr_pages + 1, nr_pages_in_file + 1))
            )
            if "appendi" in text.lower():
                return True
        return False

    def _roman_to_int(self, input_str: str) -> int:
        input_str = input_str.lower()
        roman = {
            "i": 1,
            "v": 5,
            "x": 10,
            "l": 50,
            "c": 100,
            "d": 500,
            "m": 1000,
            "iv": 4,
            "ix": 9,
            "xl": 40,
            "xc": 90,
            "cd": 400,
            "cm": 900,
        }
        i = 0
        num = 0
        while i < len(input_str):
            if i + 1 < len(input_str) and input_str[i : i + 2] in roman:
                num += roman[input_str[i : i + 2]]
                i += 2
            else:
                num += roman[input_str[i]]
                i += 1
        return num

    def _normalize_pages_str(self, *, pages: str) -> str:
        pages_str = pages

        roman_pages_matched = re.match(ROMAN_PAGES_PATTERN, pages)
        if roman_pages_matched:
            start_page, end_page = map(
                self._roman_to_int, roman_pages_matched.group().split("--")
            )
            pages_str = f"{start_page}--{end_page}"

        roman_page_matched = re.match(ROMAN_PAGE_PATTERN, pages)
        if roman_page_matched:
            page = roman_page_matched.group()
            pages_str = f"{self._roman_to_int(page)}"

        return pages_str

    def _get_expected_page_count(
        self, *, record: colrev.record.record_pdf.PDFRecord
    ) -> Optional[int]:
        try:
            pages_str = self._normalize_pages_str(pages=record.data[Fields.PAGES])
            if "--" in pages_str:
                start_page, end_page = map(int, pages_str.split("--"))
                return end_page - start_page + 1
            if "-" in pages_str:
                start_page, end_page = map(int, pages_str.split("-"))
                return end_page - start_page + 1
            return 1
        except ValueError:
            # e.g., S49--S50
            return None


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker."""
    quality_model.register_checker(PDFIncompletenessChecker(quality_model))
