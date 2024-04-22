#! /usr/bin/env python
"""Checker for pdf-incomplete."""
from __future__ import annotations

import re
from pathlib import Path

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
    """The PDFIncompletenessChecker"""

    msg = PDFDefectCodes.PDF_INCOMPLETE

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record_pdf.PDFRecord) -> None:
        """Run the pdf-incomplete checks"""

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

        def longer_with_appendix(
            *,
            record: colrev.record.record_pdf.PDFRecord,
            nr_pages: int,
        ) -> bool:
            if 10 < nr_pages < record.data[Fields.NR_PAGES_IN_FILE]:
                text = record.extract_text_by_page(
                    pages=list(
                        range(nr_pages + 1, record.data[Fields.NR_PAGES_IN_FILE] + 1)
                    )
                )
                if "appendi" in text.lower():
                    return True
            return False

        def roman_to_int(input_str: str) -> int:
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

        def get_nr_pages(*, pages: str) -> int:
            pages_str = pages

            roman_pages_matched = re.match(ROMAN_PAGES_PATTERN, pages)
            if roman_pages_matched:
                start_page, end_page = map(
                    roman_to_int, roman_pages_matched.group().split("--")
                )
                pages_str = f"{start_page}--{end_page}"

            roman_page_matched = re.match(ROMAN_PAGE_PATTERN, pages)
            if roman_page_matched:
                page = roman_page_matched.group()
                pages_str = f"{roman_to_int(page)}"

            if "--" in pages_str:
                start_page, end_page = map(int, pages_str.split("--"))
                nr_pages = end_page - start_page + 1
            else:
                nr_pages = 1
            return nr_pages

        # Get nr pages from PDF (set in quality_model)
        if Fields.NR_PAGES_IN_FILE not in record.data:
            return False

        # Not complete if there is a FULL_VERSION_PURCHASE_NOTICE
        if any(
            FULL_VERSION_PURCHASE_NOTICE
            in record.data[Fields.TEXT_FROM_PDF].lower().replace(" ", "")
            for FULL_VERSION_PURCHASE_NOTICE in FULL_VERSION_PURCHASE_NOTICES
        ):
            return False

        # Get nr pages from pages field
        try:
            nr_pages = get_nr_pages(pages=record.data[Fields.PAGES])
        except ValueError:
            # e.g., S49--S50
            return True

        # Special case: if the PDF has more pages than the pages field, it may be complete
        if longer_with_appendix(record=record, nr_pages=nr_pages):
            return True

        # If the PDF has the same number of pages as the pages field, it is complete
        return nr_pages == record.data[Fields.NR_PAGES_IN_FILE]


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(PDFIncompletenessChecker(quality_model))
