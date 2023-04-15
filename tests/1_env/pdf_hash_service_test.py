#!/usr/bin/env python
import logging
import os
import shutil
import typing
from pathlib import Path

import pytest

import colrev.env.pdf_hash_service
import colrev.exceptions as colrev_exceptions
import colrev.review_manager

test_data_path = Path()
env_dir = Path()


@pytest.fixture(scope="module")
def script_loc(request) -> Path:  # type: ignore
    """Return the directory of the currently running test script"""

    return Path(request.fspath).parent


def retrieve_test_file(*, source: Path, target: Path) -> None:
    target.parent.mkdir(exist_ok=True, parents=True)
    shutil.copy(
        test_data_path / source,
        target,
    )


@pytest.fixture(scope="module")
def pdf_hash_service(tmp_path_factory: Path, request) -> colrev.env.pdf_hash_service.PDFHashService:  # type: ignore
    global test_data_path
    global env_dir

    test_data_path = Path(request.fspath).parents[1] / Path("data")
    env_dir = tmp_path_factory.mktemp("test_repo")  # type: ignore

    os.chdir(env_dir)
    pdf_hash_service = colrev.env.pdf_hash_service.PDFHashService(
        logger=logging.getLogger("test_logger")
    )
    return pdf_hash_service


@pytest.mark.parametrize(
    "pdf_path, expected_result",
    [
        (
            Path("WagnerLukyanenkoParEtAl2022.pdf"),
            "87ffff1fffffff1ff47fff7fe0008307e000071fffffff07f1603f0ffd67fffff7ffffffe0000007e0000007e0000007fc4d59b7e3ffffffe03fffffffffffffe1ff0007e0000007e0000007e00080b7e0008007e0000007e0000007e0000007e0008007e000ffffe0008fffe000000ff00087ffffffffffffffffffffffffff",
        ),
        (Path("zero-size-pdf.pdf"), "InvalidPDFException"),
    ],
)
def test_pdf_hash_service(pdf_path, expected_result, pdf_hash_service) -> None:  # type: ignore
    target_path = env_dir / Path("data/pdfs/") / pdf_path
    retrieve_test_file(
        source=pdf_path,
        target=target_path,
    )
    if expected_result == "InvalidPDFException":
        with pytest.raises(colrev_exceptions.InvalidPDFException):
            pdf_hash_service.get_pdf_hash(pdf_path=target_path, page_nr=1, hash_size=32)
    elif expected_result == "PDFHashError":
        with pytest.raises(colrev_exceptions.PDFHashError):
            pdf_hash_service.get_pdf_hash(pdf_path=target_path, page_nr=1, hash_size=32)

    else:
        actual = pdf_hash_service.get_pdf_hash(
            pdf_path=target_path, page_nr=1, hash_size=32
        )
        assert expected_result == actual
