#!/usr/bin/env python
"""Test the colrev_pdf_id"""
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.qm.colrev_pdf_id
import colrev.review_manager


@pytest.mark.parametrize(
    "pdf_path, expected_result",
    [
        (
            Path("WagnerLukyanenkoParEtAl2022.pdf"),
            "87ffff1fffffff1ff47fff7fe0000307e000071fffffff07f1603f0ffd67fffff7ffffff"
            "e0000007e0000007e0000007fc6d59b7e3ffffffe03fffffffffffffe1ff0007e0000007"
            "e0000007e00080ffe0008007e0000007e0000007e0000007e0008007e000fdffe0008fff"
            "e000000ff00087ffffffffffffffffffffffffff",
        ),
        (Path("zero-size-pdf.pdf"), "InvalidPDFException"),
    ],
)
def test_pdf_hash(  # type: ignore
    pdf_path: Path,
    expected_result: str,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    """Test the pdf hash generation"""
    target_path = base_repo_review_manager.path / Path("data/pdfs/") / pdf_path
    helpers.retrieve_test_file(
        source=pdf_path,
        target=target_path,
    )
    if expected_result == "InvalidPDFException":
        with pytest.raises(colrev_exceptions.InvalidPDFException):
            colrev.qm.colrev_pdf_id.get_pdf_hash(
                pdf_path=target_path, page_nr=1, hash_size=32
            )
    elif expected_result == "PDFHashError":
        with pytest.raises(colrev_exceptions.PDFHashError):
            colrev.qm.colrev_pdf_id.get_pdf_hash(
                pdf_path=target_path, page_nr=1, hash_size=32
            )

    else:
        actual = colrev.qm.colrev_pdf_id.get_pdf_hash(
            pdf_path=target_path, page_nr=1, hash_size=32
        )
        assert expected_result == actual

    target_path.unlink()
