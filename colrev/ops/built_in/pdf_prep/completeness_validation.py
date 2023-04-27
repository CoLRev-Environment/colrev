#! /usr/bin/env python
"""Completeness validation as a PDF preparation operation"""
from __future__ import annotations

import re
from dataclasses import dataclass

import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
@dataclass
class PDFCompletenessValidation(JsonSchemaMixin):
    """Prepare PDFs by validating its completeness (based on the number of pages)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    roman_pages_pattern = re.compile(
        r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?--"
        + r"M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$",
        re.IGNORECASE,
    )
    roman_page_pattern = re.compile(
        r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$", re.IGNORECASE
    )

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __longer_with_appendix(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.Record,
        nr_pages_metadata: int,
    ) -> bool:
        if 10 < nr_pages_metadata < record.data["pages_in_file"]:
            text = record.extract_text_by_page(
                pages=[
                    record.data["pages_in_file"] - 3,
                    record.data["pages_in_file"] - 2,
                    record.data["pages_in_file"] - 1,
                ],
                project_path=review_manager.path,
            )
            if "appendi" in text.lower():
                return True
        return False

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,
    ) -> dict:
        """Prepare the PDF by validating completeness (based on number of pages)"""

        if colrev.record.RecordState.pdf_imported != record.data.get(
            "colrev_status", "NA"
        ):
            return record.data

        if not record.data["file"].endswith(".pdf"):
            return record.data

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
            pages=[0, 1], project_path=pdf_prep_operation.review_manager.path
        ).replace(" ", ""):
            msg = (
                f'{record.data["ID"]}'.ljust(pad - 1, " ")
                + " Not the full version of the paper"
            )
            pdf_prep_operation.review_manager.report_logger.error(msg)
            record.add_data_provenance_note(key="file", note="not_full_version")
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )
            return record.data

        pages_metadata = record.data.get("pages", "NA")

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

        if pages_metadata == "NA" or not re.match(r"^\d+--\d+|\d+$", pages_metadata):
            msg = (
                f'{record.data["ID"]}'.ljust(pad - 1, " ")
                + "Could not validate completeness: no pages in metadata"
            )
            record.add_data_provenance_note(key="file", note="no_pages_in_metadata")
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )
            return record.data

        nr_pages_metadata = __get_nr_pages_in_metadata(pages_metadata=pages_metadata)

        record.set_pages_in_pdf(project_path=pdf_prep_operation.review_manager.path)
        if nr_pages_metadata != record.data["pages_in_file"]:
            # this may become a settings option (coverpages: ok)
            # if nr_pages_metadata == int(record.data["pages_in_file"]) - 1:
            #     record.add_data_provenance_note(key="file", note="more_pages_in_pdf")

            if self.__longer_with_appendix(
                review_manager=pdf_prep_operation.review_manager,
                record=record,
                nr_pages_metadata=nr_pages_metadata,
            ):
                pass
            else:
                msg = (
                    f'{record.data["ID"]}'.ljust(pad, " ")
                    + f'Nr of pages in file ({record.data["pages_in_file"]}) '
                    + "not identical with record "
                    + f"({nr_pages_metadata} pages)"
                )

                record.add_data_provenance_note(
                    key="file", note="nr_pages_not_matching"
                )
                record.data.update(
                    colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
                )

        return record.data


if __name__ == "__main__":
    pass
