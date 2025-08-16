#!/usr/bin/env python
"""Tests for the PDF quality model"""
from __future__ import annotations

from pathlib import Path

import colrev.record.qm.quality_model
import colrev.record.record_pdf
from colrev.constants import Fields
from colrev.constants import PDFDefectCodes
from colrev.constants import RecordState


def test_pdf_qm(  # type: ignore
    v_t_pdf_record: colrev.record.record_pdf.PDFRecord,
    pdf_quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    """Test pdf-qm"""

    original_title = v_t_pdf_record.data.pop(Fields.TITLE, None)

    v_t_pdf_record.run_pdf_quality_model(pdf_qm=pdf_quality_model)

    assert not v_t_pdf_record.has_pdf_defects()
    assert [] == v_t_pdf_record.get_field_provenance_notes(Fields.FILE)

    v_t_pdf_record.data[Fields.TITLE] = original_title

    v_t_pdf_record.run_pdf_quality_model(pdf_qm=pdf_quality_model)

    original_filepath = Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf")
    v_t_pdf_record.data.pop(Fields.FILE, None)
    v_t_pdf_record.run_pdf_quality_model(pdf_qm=pdf_quality_model)
    v_t_pdf_record.data[Fields.FILE] = original_filepath


def test_author_not_in_pdf(
    v_t_pdf_record: colrev.record.record_pdf.PDFRecord,
    pdf_quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    from colrev.record.qm.pdf_checkers.author_not_in_pdf import (
        AuthorNotInPDFChecker,
    )

    # Setup: Instantiate the AuthorNotInPDFChecker directly
    author_not_in_pdf_checker = AuthorNotInPDFChecker(pdf_quality_model)

    # Test case 1: Author not found in PDF
    v_t_pdf_record.data[Fields.AUTHOR] = "Smith, John"
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    )
    author_not_in_pdf_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        PDFDefectCodes.AUTHOR_NOT_IN_PDF
    ]

    # Test case 2: Author found in PDF
    v_t_pdf_record.data[Fields.AUTHOR] = "Smith, John"
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = (
        "Paper title by Smith, John. Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    )
    author_not_in_pdf_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == []

    # Test case 3: Ignoring author not in PDF defect
    v_t_pdf_record.data[Fields.AUTHOR] = "Smith, John"
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    )
    v_t_pdf_record.ignore_defect(
        key=Fields.FILE, defect=PDFDefectCodes.AUTHOR_NOT_IN_PDF
    )
    author_not_in_pdf_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        f"IGNORE:{PDFDefectCodes.AUTHOR_NOT_IN_PDF}"
    ]

    # Test case 4: "editorial" in title
    v_t_pdf_record.data[Fields.AUTHOR] = "Smith, John"
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = (
        "Editorial title. Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    )
    v_t_pdf_record.data.pop(Fields.D_PROV, None)
    v_t_pdf_record.data[Fields.TITLE] = (
        "Editorial: The Importance of AI in Software Development"
    )
    author_not_in_pdf_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == []


def test_title_not_in_pdf(
    v_t_pdf_record: colrev.record.record_pdf.PDFRecord,
    pdf_quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    from colrev.record.qm.pdf_checkers.title_not_in_pdf import TitleNotInPDFChecker

    # Setup: Instantiate the TitleNotInPDFChecker directly
    title_not_in_pdf_checker = TitleNotInPDFChecker(pdf_quality_model)

    # Test case 1: Title not found in PDF
    v_t_pdf_record.data[Fields.TITLE] = "Sample Title"
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    )
    title_not_in_pdf_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        PDFDefectCodes.TITLE_NOT_IN_PDF
    ]


def test_no_text_in_pdf(
    v_t_pdf_record: colrev.record.record_pdf.PDFRecord,
    pdf_quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    from colrev.record.qm.pdf_checkers.no_text_in_pdf import TextInPDFChecker

    # Setup: Instantiate the TextInPDFChecker directly
    no_text_in_pdf_checker = TextInPDFChecker(pdf_quality_model)

    # Test case 1: No text in PDF
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = ""
    no_text_in_pdf_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        PDFDefectCodes.NO_TEXT_IN_PDF
    ]

    # Test case 2: Text present in PDF
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    )
    v_t_pdf_record.data.pop(Fields.D_PROV, None)
    no_text_in_pdf_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == []

    # Test case 3: Ignoring no text in PDF defect
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = ""
    v_t_pdf_record.ignore_defect(key=Fields.FILE, defect=PDFDefectCodes.NO_TEXT_IN_PDF)
    no_text_in_pdf_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        f"IGNORE:{PDFDefectCodes.NO_TEXT_IN_PDF}"
    ]


def test_pdf_incompleteness(
    v_t_pdf_record: colrev.record.record_pdf.PDFRecord,
    pdf_quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    from colrev.record.qm.pdf_checkers.pdf_incomplete import PDFIncompletenessChecker

    # Setup: Instantiate the PDFIncompletenessChecker directly
    pdf_incompleteness_checker = PDFIncompletenessChecker(pdf_quality_model)

    original_filepath = Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf")
    # Note: TEXT_FROM_PDF and NR_PAGES_IN_FILE are set by quality_model
    # For the tests, we do not call the quality_model, but set the fields directly
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = "test"
    v_t_pdf_record.data[Fields.NR_PAGES_IN_FILE] = 18

    # Test case 1: PDF is incomplete
    v_t_pdf_record.data[Fields.FILE] = Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf")
    v_t_pdf_record.data[Fields.PAGES] = "1--10"
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        PDFDefectCodes.PDF_INCOMPLETE
    ]

    # Test case 2: PDF is complete
    v_t_pdf_record.data[Fields.FILE] = Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf")
    v_t_pdf_record.data[Fields.PAGES] = "209--226"
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == []

    # Test case 3: PDF is complete (with roman numbers)
    v_t_pdf_record.data[Fields.FILE] = Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf")
    v_t_pdf_record.data[Fields.PAGES] = "IX--XXVI"
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == []

    # Test case 4: PDF is complete (S-prefixed numbers)
    v_t_pdf_record.data[Fields.FILE] = Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf")
    v_t_pdf_record.data[Fields.PAGES] = "S9--S16"
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == []

    # Test case 5: Ignoring pdf incomplete defect
    v_t_pdf_record.data[Fields.FILE] = Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf")
    v_t_pdf_record.data[Fields.PAGES] = "1--10"
    v_t_pdf_record.ignore_defect(key=Fields.FILE, defect=PDFDefectCodes.PDF_INCOMPLETE)
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        f"IGNORE:{PDFDefectCodes.PDF_INCOMPLETE}"
    ]
    v_t_pdf_record.data.pop(Fields.D_PROV, None)

    # Test case 6: Pages do not match PDF
    v_t_pdf_record.data[Fields.PAGES] = "1--10"
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        PDFDefectCodes.PDF_INCOMPLETE
    ]

    # Test case 7: Purchase-full-version notice
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = (
        "morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas"
    )
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        PDFDefectCodes.PDF_INCOMPLETE
    ]
    v_t_pdf_record.data.pop(Fields.D_PROV, None)

    # Test case 8: Pages match PDF
    v_t_pdf_record.data[Fields.FILE] = original_filepath
    v_t_pdf_record.data[Fields.PAGES] = "209--226"
    v_t_pdf_record.data[Fields.TEXT_FROM_PDF] = "test"
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == []
    v_t_pdf_record.data.pop(Fields.D_PROV, None)

    # Test case 9: Longer with appendix and "appendi" in text
    v_t_pdf_record.data[Fields.FILE] = original_filepath
    v_t_pdf_record.data[Fields.PAGES] = "1--20"
    v_t_pdf_record.data[Fields.NR_PAGES_IN_FILE] = 30

    def patched_extract_text_by_page(self, *, pages):  # type: ignore
        return "This is a paper with appendix attached (ie., more pages)"

    original_method = colrev.record.record_pdf.PDFRecord.extract_text_by_page
    colrev.record.record_pdf.PDFRecord.extract_text_by_page = patched_extract_text_by_page  # type: ignore

    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == []
    colrev.record.record_pdf.PDFRecord.extract_text_by_page = original_method  # type: ignore
    v_t_pdf_record.data[Fields.NR_PAGES_IN_FILE] = 18

    # Test case 10: PDF is incomplete (with roman numbers)
    v_t_pdf_record.data[Fields.FILE] = Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf")
    v_t_pdf_record.data[Fields.PAGES] = "XXVI"
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        PDFDefectCodes.PDF_INCOMPLETE
    ]

    # Test case 11: NR_PAGES_IN_PDF not set
    v_t_pdf_record.data[Fields.FILE] = original_filepath
    v_t_pdf_record.data[Fields.PAGES] = "1--20"

    v_t_pdf_record.data.pop(Fields.NR_PAGES_IN_FILE, None)
    pdf_incompleteness_checker.run(record=v_t_pdf_record)
    assert v_t_pdf_record.get_field_provenance_notes(Fields.FILE) == [
        PDFDefectCodes.PDF_INCOMPLETE
    ]
    v_t_pdf_record.data[Fields.NR_PAGES_IN_FILE] = 18


def test_run_pdf_quality_model(  # type: ignore
    mocker,
    v_t_pdf_record,
    pdf_quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:

    mocker.patch(
        "colrev.record.record.Record.has_pdf_defects",
        return_value=True,
    )
    v_t_pdf_record.run_pdf_quality_model(pdf_quality_model)
    assert (
        v_t_pdf_record.data[Fields.STATUS] == RecordState.pdf_needs_manual_preparation
    )

    mocker.patch(
        "colrev.record.record.Record.has_pdf_defects",
        return_value=False,
    )
    v_t_pdf_record.run_pdf_quality_model(pdf_quality_model, set_prepared=True)
    assert v_t_pdf_record.data[Fields.STATUS] == RecordState.pdf_prepared
