#!/usr/bin/env python
"""Test the colrev_pdf_id"""
import os
from pathlib import Path

import fitz
import imagehash
import pytest
from PIL import Image

import colrev.exceptions as colrev_exceptions
import colrev.record.record_identifier


@pytest.mark.parametrize(
    "pdf_path, expected_result",
    [
        (
            Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
            "cpid2:87ffff1fffffff1ff47fff7fe0000307e000071fffffff07f1603f0ffd67fffff7ffffff"
            "e0000007e0000007e0000007fc6d59b7e3ffffffe03fffffffffffffe1ff0007e0000007"
            "e0000007e00080ffe0008007e0000007e0000007e0000007e0008007e000fdffe0008fff"
            "e000000ff00087ffffffffffffffffffffffffff",
        ),
        (Path("data/zero-size-pdf.pdf"), "InvalidPDFException"),
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
            colrev.record.record.Record.get_colrev_pdf_id(pdf_path=target_path)
    elif expected_result == "PDFHashError":
        with pytest.raises(colrev_exceptions.PDFHashError):
            colrev.record.record.Record.get_colrev_pdf_id(pdf_path=target_path)

    else:
        actual = colrev.record.record.Record.get_colrev_pdf_id(pdf_path=target_path)
        assert expected_result == actual


def test_open_pdf_invalid_path(helpers, tmp_path):  # type: ignore
    """Test the open pdf with invalid path"""
    os.chdir(tmp_path)

    pdf_path = Path("data/WagnerLukyanenkoParEtAl2022.pdf")
    helpers.retrieve_test_file(
        source=pdf_path,
        target=pdf_path,
    )

    def fitz_open_file_data_error(pdf_path):  # type: ignore
        """Raise a file data error"""
        raise fitz.fitz.FileDataError("Invalid PDF")

    original_fitz_open = fitz.open
    fitz.open = fitz_open_file_data_error

    with pytest.raises(colrev_exceptions.InvalidPDFException):
        colrev.record.record.Record.get_colrev_pdf_id(pdf_path=pdf_path)

    fitz.open = original_fitz_open

    def image_open_runtime_error(pdf_path):  # type: ignore
        """Raise a runtime error"""
        raise RuntimeError

    original_image_open = Image.open
    Image.open = image_open_runtime_error

    with pytest.raises(colrev_exceptions.PDFHashError):
        colrev.record.record.Record.get_colrev_pdf_id(pdf_path=pdf_path)

    Image.open = original_image_open

    original_imagehash_averagehash = imagehash.average_hash

    # pylint: disable=unused-argument
    def imagehash_0000_hash(pdf_path, hash_size):  # type: ignore
        return "000000000000"

    imagehash.average_hash = imagehash_0000_hash

    with pytest.raises(colrev_exceptions.PDFHashError):
        colrev.record.record.Record.get_colrev_pdf_id(pdf_path=pdf_path)

    imagehash.average_hash = original_imagehash_averagehash

    # with pytest.raises(NotImplementedError):
    #     colrev.record.record.Record.get_colrev_pdf_id(
    #         pdf_path=pdf_path, cpid_version="unknown"
    #     )

    pdf_path.unlink(missing_ok=True)


def test_cpid(helpers) -> None:  # type: ignore

    pdf_path = Path("data/WagnerLukyanenkoParEtAl2022.pdf")
    helpers.retrieve_test_file(
        source=pdf_path,
        target=pdf_path,
    )
    with pytest.raises(NotImplementedError):
        colrev.record.record_identifier.create_colrev_pdf_id(
            pdf_path=pdf_path, cpid_version="unknown"
        )
