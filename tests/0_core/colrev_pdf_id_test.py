#!/usr/bin/env python
import os
import shutil
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.qm.colrev_pdf_id
import colrev.review_manager

test_data_path = Path()


@pytest.fixture(scope="module")
def env_dir(tmp_path_factory: Path, request) -> Path:  # type: ignore
    """Initialize the environment directory"""
    global test_data_path

    test_data_path = Path(request.fspath).parents[1] / Path("data")
    env_directory = tmp_path_factory.mktemp("test_repo")  # type: ignore

    os.chdir(env_directory)
    return env_directory


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
def test_pdf_hash_service(pdf_path, expected_result, env_dir) -> None:  # type: ignore
    target_path = env_dir / Path("data/pdfs/") / pdf_path
    retrieve_test_file(
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
