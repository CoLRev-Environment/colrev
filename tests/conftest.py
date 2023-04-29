#!/usr/bin/env python
"""Conftest file containing fixtures to set up tests efficiently"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

import colrev.review_manager

# Note : the following produces different relative paths locally/on github.
# Path(colrev.__file__).parents[1]


# pylint: disable=too-few-public-methods
class Helpers:
    """Helpers class providing utility functions (e.g., for test-file retrieval)"""

    test_data_path = Path(__file__).parent / Path("data")

    @staticmethod
    def retrieve_test_file(*, source: Path, target: Path) -> None:
        """Retrieve a test file"""
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy(
            Helpers.test_data_path / source,
            target,
        )


@pytest.fixture(scope="session")
def helpers():  # type: ignore
    """Fixture returning Helpers"""
    return Helpers


@pytest.fixture(scope="session", name="base_repo_review_manager")
def fixture_base_repo_review_manager(session_mocker, tmp_path_factory):  # type: ignore
    """Fixture returning the base review_manager"""
    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.register_repo",
        return_value=(),
    )
    test_repo_dir = tmp_path_factory.mktemp("base_repo")  # type: ignore
    os.chdir(test_repo_dir)
    colrev.review_manager.get_init_operation(
        review_type="literature_review",
        target_path=test_repo_dir,
    )
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    return review_manager


@pytest.fixture(scope="module")
def language_service() -> colrev.env.language_service.LanguageService:  # type: ignore
    """Return a language service object"""

    return colrev.env.language_service.LanguageService()


@pytest.fixture(scope="package")
def prep_operation(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> colrev.ops.prep.Prep:
    """Fixture returning a prep operation"""
    return base_repo_review_manager.get_prep_operation()


@pytest.fixture
def record_with_pdf() -> colrev.record.Record:
    """Fixture returning a record containing a file (PDF)"""
    return colrev.record.Record(
        data={
            "ID": "WagnerLukyanenkoParEtAl2022",
            "ENTRYTYPE": "article",
            "file": Path("WagnerLukyanenkoParEtAl2022.pdf"),
        }
    )
