#!/usr/bin/env python
"""Test record identification"""
import os
from pathlib import Path

import imagehash
import pymupdf
import pytest
from PIL import Image

import colrev.exceptions as colrev_exceptions
import colrev.record.record
import colrev.record.record_identifier
import colrev.review_manager


# pylint: disable=line-too-long
# flake8: noqa


@pytest.mark.parametrize(
    "record_dict, colrev_id",
    [
        (
            {
                "ENTRYTYPE": "article",
                "ID": "Staehr2010",
                "author": 'Staehr, Lorraine "Emma"',
                "journal": "Information Systems Journal",
                "title": "Understanding the role of managerial agency in achieving business benefits from ERP systems",
                "year": "2010",
                "volume": "20",
                "number": "3",
                "pages": "213--238",
            },
            "colrev_id1:|a|information-systems-journal|20|3|2010|staehr|understanding-the-role-of-managerial-agency-in-achieving-business-benefits-from-erp-systems",
        ),
        (
            {
                "ENTRYTYPE": "article",
                "ID": "WebsterWatson2002",
                "author": "Webster, and Watson,",
                "journal": "MIS Quarterly",
                "title": "Analyzing the past to prepare for the future: Writing a literature review",
                "year": "2002",
                "volume": "26",
                "number": "2",
                "pages": "13--23",
            },
            "colrev_id1:|a|mis-quarterly|26|2|2002|webster-watson|analyzing-the-past-to-prepare-for-the-future-writing-a-literature-review",
        ),
        (
            {
                "ENTRYTYPE": "article",
                "ID": "WebsterWatson2002",
                "author": "UNKNOWN",
                "journal": "MIS Quarterly",
                "title": "Analyzing the past to prepare for the future: Writing a literature review",
                "year": "2002",
                "volume": "26",
                "number": "2",
                "pages": "13--23",
            },
            "NotEnoughDataToIdentifyException",
        ),
        (
            {
                "ENTRYTYPE": "inproceedings",
                "ID": "Smith2002",
                "author": "Smith, Tom",
                "booktitle": "HICSS",
                "title": "Minitrack introduction",
                "year": "2002",
            },
            "NotEnoughDataToIdentifyException",
        ),
        (
            {
                "ENTRYTYPE": "article",
                "ID": "WebsterWatson2002",
                "author": "",
                "journal": "MIS Quarterly",
                "title": "Analyzing the past to prepare for the future: Writing a literature review",
                "year": "2002",
                "volume": "26",
                "number": "2",
                "pages": "13--23",
            },
            "NotEnoughDataToIdentifyException",
        ),
    ],
)
def test_colrev_id(  # type: ignore
    record_dict: dict,
    colrev_id: str,
) -> None:
    """Test the colrev_id generation"""

    if colrev_id == "NotEnoughDataToIdentifyException":
        with pytest.raises(colrev_exceptions.NotEnoughDataToIdentifyException):
            colrev.record.record.Record(record_dict).get_colrev_id(
                assume_complete=False,
            )
        return

    actual = colrev.record.record.Record(record_dict).get_colrev_id(
        assume_complete=False,
    )
    assert actual == colrev_id


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

    def pympdf_open_file_data_error(pdf_path):  # type: ignore
        """Raise a file data error"""
        raise pymupdf.FileDataError("Invalid PDF")

    original_fitz_open = pymupdf.open
    pymupdf.open = pympdf_open_file_data_error

    with pytest.raises(colrev_exceptions.InvalidPDFException):
        colrev.record.record.Record.get_colrev_pdf_id(pdf_path=pdf_path)

    pymupdf.open = original_fitz_open

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
    """Test for cpid"""

    pdf_path = Path("data/WagnerLukyanenkoParEtAl2022.pdf")
    helpers.retrieve_test_file(
        source=pdf_path,
        target=pdf_path,
    )
    with pytest.raises(NotImplementedError):
        colrev.record.record_identifier.get_colrev_pdf_id(
            pdf_path=pdf_path, cpid_version="unknown"
        )
