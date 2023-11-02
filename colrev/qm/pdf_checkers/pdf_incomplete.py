#! /usr/bin/env python
"""Checker for pdf-incomplete."""
from __future__ import annotations

import re
from pathlib import Path

import colrev.env.utils
import colrev.qm.quality_model
from colrev.constants import Fields
from colrev.constants import PDFDefectCodes

# pylint: disable=too-few-public-methods

# Note: replaces author_not_in_first_pages


class PDFIncompletenessChecker:
    """The PDFIncompletenessChecker"""

    msg = PDFDefectCodes.PDF_INCOMPLETE

    roman_pages_pattern = re.compile(
        r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?--"
        + r"M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$",
        re.IGNORECASE,
    )
    roman_page_pattern = re.compile(
        r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$", re.IGNORECASE
    )

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the pdf-incomplete checks"""

        if (
            Fields.FILE not in record.data
            or Path(record.data[Fields.FILE]).suffix != ".pdf"
            or Fields.PAGES not in record.data
            or record.ignored_defect(field=Fields.FILE, defect=self.msg)
        ):
            return

        if not self.__pages_match_pdf(record=record):
            record.add_data_provenance_note(key=Fields.FILE, note=self.msg)
        else:
            record.remove_data_provenance_note(key=Fields.FILE, note=self.msg)

    def __longer_with_appendix(
        self,
        *,
        record: colrev.record.Record,
        nr_pages_metadata: int,
    ) -> bool:
        if 10 < nr_pages_metadata < record.data[Fields.PAGES_IN_FILE]:
            text = record.extract_text_by_page(
                pages=[
                    record.data[Fields.PAGES_IN_FILE] - 3,
                    record.data[Fields.PAGES_IN_FILE] - 2,
                    record.data[Fields.PAGES_IN_FILE] - 1,
                ],
            )
            if "appendi" in text.lower():
                return True
        return False

    def __pages_match_pdf(self, *, record: colrev.record.Record) -> bool:
        def __roman_to_int(*, s: str) -> int:
            s = s.lower()
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
            while i < len(s):
                if i + 1 < len(s) and s[i : i + 2] in roman:
                    num += roman[s[i : i + 2]]
                    i += 2
                else:
                    num += roman[s[i]]
                    i += 1
            return num

        def __get_nr_pages_in_metadata(*, pages_metadata: str) -> int:
            if "--" in pages_metadata:
                nr_pages_metadata = (
                    int(pages_metadata.split("--")[1])
                    - int(pages_metadata.split("--")[0])
                    + 1
                )
            else:
                nr_pages_metadata = 1
            return nr_pages_metadata

        full_version_purchase_notice = (
            "morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas"
        )
        if full_version_purchase_notice in record.extract_text_by_page(
            pages=[0, 1]
        ).replace(" ", ""):
            return False

        pages_metadata = record.data.get(Fields.PAGES, "NA")

        roman_pages_matched = re.match(self.roman_pages_pattern, pages_metadata)
        if roman_pages_matched:
            start_page, end_page = roman_pages_matched.group().split("--")
            pages_metadata = (
                f"{__roman_to_int(s=start_page)}--{__roman_to_int(s=end_page)}"
            )
        roman_page_matched = re.match(self.roman_page_pattern, pages_metadata)
        if roman_page_matched:
            page = roman_page_matched.group()
            pages_metadata = f"{__roman_to_int(s=page)}"

        try:
            nr_pages_metadata = __get_nr_pages_in_metadata(
                pages_metadata=pages_metadata
            )
        except ValueError:
            # e.g., S49--S50
            return True

        record.set_pages_in_pdf()
        if Fields.PAGES_IN_FILE not in record.data:
            return True

        if nr_pages_metadata == record.data[Fields.PAGES_IN_FILE]:
            return True

        if self.__longer_with_appendix(
            record=record,
            nr_pages_metadata=nr_pages_metadata,
        ):
            return True

        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(PDFIncompletenessChecker(quality_model))
