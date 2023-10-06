#!/usr/bin/env python
"""Tests of the CoLRev pdf-get operation"""
from pathlib import Path
from unittest.mock import patch

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.review_manager


# def test_pdf_get(  # type: ignore
#     base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
# ) -> None:
#     """Test the pdf-get operation"""

#     helpers.reset_commit(
#         review_manager=base_repo_review_manager, commit="prescreen_commit"
#     )

#     pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
#         notify_state_transition_operation=True
#     )
#   pdf_get_operation.main()


def test_pdf_get_import_file(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the pdf-get import_file()"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="prescreen_commit"
    )

    pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )

    helpers.retrieve_test_file(
        source=Path("SrivastavaShainesh2015.pdf"),
        target=Path("data/pdfs/SrivastavaShainesh2015.pdf"),
    )
    pdf_get_operation.import_pdf(
        record=colrev.record.Record(
            data={"ID": "SrivastavaShainesh2015", "file": "SrivastavaShainesh2015.pdf"}
        )
    )
    base_repo_review_manager.settings.pdf_get.pdf_path_type = (
        colrev.settings.PDFPathType.copy
    )

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="prescreen_commit"
    )

    pdf_get_operation.import_pdf(
        record=colrev.record.Record(
            data={"ID": "SrivastavaShainesh2015", "file": "SrivastavaShainesh2015.pdf"}
        )
    )


# def test_pdf_get_link_pdf(  # type: ignore
#     base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
# ) -> None:
#     """Test the pdf-get link_pdf()"""


def test_pdf_get_setup_custom_script(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the pdf-get setup_custom_script()"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="prescreen_commit"
    )

    pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.setup_custom_script()


def test_pdf_get_copy_pdfs_to_repo(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the pdf-get copy_pdfs_to_repo()"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="pdf_get_commit"
    )

    pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    records = pdf_get_operation.review_manager.dataset.load_records_dict()
    for record in records.values():
        record["file"] = record["ID"] + ".pdf"
    pdf_get_operation.review_manager.dataset.save_records_dict(records=records)
    pdf_get_operation.copy_pdfs_to_repo()

    records = pdf_get_operation.review_manager.dataset.load_records_dict()
    for record in records.values():
        if "file" in record:
            del record["file"]
    pdf_get_operation.review_manager.dataset.save_records_dict(records=records)
    pdf_get_operation.copy_pdfs_to_repo()


def test_pdf_get_get_target_filepath(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the pdf-get get_target_filepath()"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="pdf_get_commit"
    )

    pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )

    record_dict = {
        "ID": "SrivastavaShainesh2015",
        "year": "2015",
        "file": "SrivastavaShainesh2015.pdf",
        "volume": "43",
        "number": "1",
    }

    actual = pdf_get_operation.get_target_filepath(
        record=colrev.record.Record(data=record_dict)
    )
    expected = Path("data/pdfs/SrivastavaShainesh2015.pdf")
    assert actual == expected

    pdf_get_operation.filepath_directory_pattern = "year"
    actual = pdf_get_operation.get_target_filepath(
        record=colrev.record.Record(data=record_dict)
    )
    expected = Path("data/pdfs/2015/SrivastavaShainesh2015.pdf")
    assert actual == expected

    pdf_get_operation.filepath_directory_pattern = "volume_number"
    actual = pdf_get_operation.get_target_filepath(
        record=colrev.record.Record(data=record_dict)
    )
    expected = Path("data/pdfs/43/1/SrivastavaShainesh2015.pdf")
    assert actual == expected

    del record_dict["number"]
    pdf_get_operation.filepath_directory_pattern = "volume_number"
    actual = pdf_get_operation.get_target_filepath(
        record=colrev.record.Record(data=record_dict)
    )
    expected = Path("data/pdfs/43/SrivastavaShainesh2015.pdf")
    assert actual == expected


# def test_pdf_get_get_relink_pdfs(  # type: ignore
#     base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
# ) -> None:
#     """Test the pdf-get get_relink_pdfs()"""

#     helpers.reset_commit(
#         review_manager=base_repo_review_manager, commit="pdf_get_commit"
#     )

#     pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
#         notify_state_transition_operation=True
#     )
#     original_source = base_repo_review_manager.settings.sources[0]
#     base_repo_review_manager.settings.sources[0].endpoint = "colrev.files_dir"
#     base_repo_review_manager.settings.sources[0].search_parameters = {
#         "scope": {"path": "pdfs"}
#     }
#   pdf_get_operation.relink_pdfs()

#   helpers.retrieve_test_file(
#       source=Path("SrivastavaShainesh2015.pdf"),
#       target=Path("data/pdfs/Srivastava2015.pdf"),
#   )
#   pdf_get_operation.import_pdf(
#       record=colrev.record.Record(
#           data={"ID": "SrivastavaShainesh2015", "file": "SrivastavaShainesh2015.pdf"}
#       )
#   )
#   base_repo_review_manager.settings.sources[0] = original_source


# TODO : collect ci_environment tests in a single test script
@patch("colrev.review_manager.ReviewManager.in_ci_environment")
def test_pdf_get_ci_environemnt(  # type: ignore
    ci_env_patcher,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    """Test the pdf-get in ci_environemnt"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="prescreen_commit"
    )

    pdf_get_operation = base_repo_review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    ci_env_patcher.return_value = True
    with pytest.raises(colrev_exceptions.ServiceNotAvailableException):
        pdf_get_operation.main()
