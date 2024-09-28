#!/usr/bin/env python
"""Tests of the Record class"""
from pathlib import Path

import imagehash
import pymupdf
import pytest
from PIL import Image

import colrev.exceptions as colrev_exceptions
import colrev.record.record_pdf
from colrev.constants import Fields

# pylint: disable=line-too-long

# flake8: noqa: E501


def test_set_text_from_pdf(helpers, record_with_pdf: colrev.record.record_pdf.PDFRecord) -> None:  # type: ignore
    """Test record.set_text_from_pdf()"""
    helpers.retrieve_test_file(
        source=Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
        target=Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"),
    )

    expected = (
        (helpers.test_data_path / Path("data/WagnerLukyanenkoParEtAl2022_content.txt"))
        .read_text(encoding="utf-8")
        .replace("\n", " ")
    )
    record_with_pdf.set_text_from_pdf()
    actual = record_with_pdf.data["text_from_pdf"]
    actual = actual[0:4219]
    assert expected == actual


def test_extract_text_by_page(  # type: ignore
    helpers, record_with_pdf: colrev.record.record_pdf.PDFRecord
) -> None:
    """Test record.extract_text_by_page()"""
    helpers.retrieve_test_file(
        source=Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
        target=Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"),
    )

    expected = (
        helpers.test_data_path / Path("data/WagnerLukyanenkoParEtAl2022_content.txt")
    ).read_text(encoding="utf-8")
    actual = record_with_pdf.extract_text_by_page(pages=[0])
    actual = actual.rstrip()
    if expected != actual:
        (
            helpers.test_data_path
            / Path("data/WagnerLukyanenkoParEtAl2022_content.txt")
        ).write_text(actual, encoding="utf-8")

    assert expected == actual


def test_set_nr_pages_in_pdf(helpers, record_with_pdf: colrev.record.record_pdf.PDFRecord) -> None:  # type: ignore
    """Test record.set_pages_in_pdf()"""
    helpers.retrieve_test_file(
        source=Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
        target=Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"),
    )
    expected = 18
    record_with_pdf.set_nr_pages_in_pdf()
    actual = record_with_pdf.data[Fields.NR_PAGES_IN_FILE]
    assert expected == actual


def test_get_pdf_hash(helpers) -> None:  # type: ignore

    with pytest.raises(colrev_exceptions.InvalidPDFException):
        colrev.record.record_pdf.PDFRecord(
            {"ID": "WagnerLukyanenkoParEtAl2022.pdf"}, path=helpers.test_data_path
        ).get_pdf_hash(page_nr=1)

    pdf_path = Path("WagnerLukyanenkoParEtAl2022.pdf")
    pdf_path.touch()
    with pytest.raises(colrev_exceptions.InvalidPDFException):
        colrev.record.record_pdf.PDFRecord(
            {
                "file": Path("WagnerLukyanenkoParEtAl2022.pdf"),
                "ID": "WagnerLukyanenkoParEtAl2022",
            },
            path=helpers.test_data_path,
        ).get_pdf_hash(page_nr=1)

    helpers.retrieve_test_file(
        source=Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
        target=pdf_path,
    )
    pdf_hash = colrev.record.record_pdf.PDFRecord(
        {
            "file": Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
            "ID": "WagnerLukyanenkoParEtAl2022",
        },
        path=helpers.test_data_path,
    ).get_pdf_hash(page_nr=1)
    assert (
        pdf_hash
        == "87ffff1fffffff1ff47fff7fe0000307e000071fffffff07f1603f0ffd67fffff7ffffffe0000007e0000007e0000007fc6d59b7e3ffffffe03fffffffffffffe1ff0007e0000007e0000007e00080ffe0008007e0000007e0000007e0000007e0008007e000fdffe0008fffe000000ff00087ffffffffffffffffffffffffff"
    )
    pdf_hash = colrev.record.record_pdf.PDFRecord(
        {"file": Path("data/WagnerLukyanenkoParEtAl2022.pdf")},
        path=helpers.test_data_path,
    ).get_pdf_hash(page_nr=1, hash_size=16)
    assert (
        pdf_hash == "fff3c3f3c3b3fff7c27fc001c7ffdfffc001c003c001c001c003c01fffffffff"
    )

    def pymupdf_open_file_data_error(pdf_path):  # type: ignore
        """Raise a file data error"""
        raise pymupdf.FileDataError("Invalid PDF")

    original_pymupdf_open = pymupdf.open
    pymupdf.open = pymupdf_open_file_data_error

    with pytest.raises(colrev_exceptions.InvalidPDFException):
        colrev.record.record_pdf.PDFRecord(
            {"file": Path("data/WagnerLukyanenkoParEtAl2022.pdf")},
            path=helpers.test_data_path,
        ).get_pdf_hash(page_nr=1)

    pymupdf.open = original_pymupdf_open

    def image_open_runtime_error(pdf_path):  # type: ignore
        """Raise a runtime error"""
        raise RuntimeError

    original_image_open = Image.open
    Image.open = image_open_runtime_error

    with pytest.raises(colrev_exceptions.PDFHashError):
        colrev.record.record_pdf.PDFRecord(
            {"file": Path("data/WagnerLukyanenkoParEtAl2022.pdf")},
            path=helpers.test_data_path,
        ).get_pdf_hash(page_nr=1)

    Image.open = original_image_open

    original_imagehash_averagehash = imagehash.average_hash

    # pylint: disable=unused-argument
    def imagehash_0000_hash(pdf_path, hash_size):  # type: ignore
        return "000000000000"

    imagehash.average_hash = imagehash_0000_hash

    with pytest.raises(colrev_exceptions.PDFHashError):
        colrev.record.record_pdf.PDFRecord(
            {"file": Path("data/WagnerLukyanenkoParEtAl2022.pdf")},
            path=helpers.test_data_path,
        ).get_pdf_hash(page_nr=1)

    imagehash.average_hash = original_imagehash_averagehash
