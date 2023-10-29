#!/usr/bin/env python
"""Tests for the PDF quality model"""
from __future__ import annotations

from pathlib import Path

import pytest

import colrev.qm.quality_model
import colrev.record
import colrev.review_manager
from colrev.constants import Fields
from colrev.constants import PDFDefectCodes


@pytest.mark.parametrize(
    "changes, defects",
    [
        (
            {Fields.TEXT_FROM_PDF: ""},
            {PDFDefectCodes.NO_TEXT_IN_PDF},
        ),
        (
            {Fields.TEXT_FROM_PDF: "This paper focuses on a different topic"},
            {PDFDefectCodes.AUTHOR_NOT_IN_PDF, PDFDefectCodes.TITLE_NOT_IN_PDF},
        ),
        ({Fields.TEXT_FROM_PDF: Path("WagnerLukyanenkoParEtAl2022_content.txt")}, {}),
        (
            {
                Fields.TEXT_FROM_PDF: Path("WagnerLukyanenkoParEtAl2022_content.txt"),
                Fields.PAGES: "209--211",
            },
            {PDFDefectCodes.PDF_INCOMPLETE},
        ),
    ],
)
def test_get_quality_defects_author(  # type: ignore
    changes: dict,
    defects: set,
    v_t_record: colrev.record.Record,
    pdf_quality_model: colrev.qm.quality_model.QualityModel,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    """Test record.get_quality_defects() - author field"""

    helpers.retrieve_test_file(
        source=Path("WagnerLukyanenkoParEtAl2022.pdf"),
        target=base_repo_review_manager.path
        / Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"),
    )

    # Activate PDF file or text_from_pdf
    for key, value in changes.items():
        if isinstance(value, Path):
            v_t_record.data[key] = (helpers.test_data_path / value).read_text(
                encoding="utf-8"
            )
        else:
            v_t_record.data[key] = value

    v_t_record.run_pdf_quality_model(pdf_qm=pdf_quality_model)

    if not defects:
        assert not v_t_record.has_pdf_defects()
    else:
        assert v_t_record.has_pdf_defects()
        actual = set(v_t_record.data[Fields.D_PROV][Fields.FILE]["note"].split(","))
        assert defects == actual
