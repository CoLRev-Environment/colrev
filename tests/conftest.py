#!/usr/bin/env python
"""Conftest file containing fixtures to set up tests efficiently"""
from __future__ import annotations

import os
import shutil
import typing
from pathlib import Path

import pytest
from pybtex.database.input import bibtex

import colrev.review_manager

# Note : the following produces different relative paths locally/on github.
# Path(colrev.__file__).parents[1]

# pylint: disable=line-too-long


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


@pytest.fixture(scope="session", name="helpers")
def get_helpers():  # type: ignore
    """Fixture returning Helpers"""
    return Helpers


@pytest.fixture(scope="session", name="test_local_index_dir")
def get_test_local_index_dir(tmp_path_factory):  # type: ignore
    """Fixture returning the test_local_index_dir"""
    return tmp_path_factory.mktemp("local_index")


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


@pytest.fixture(scope="session", name="local_index_test_records_dict")
def get_local_index_test_records_dict(helpers, test_local_index_dir) -> dict:  # type: ignore
    """Test records dict for local_index"""
    local_index_test_records_dict: typing.Dict[Path, dict] = {}
    bib_files_to_index = helpers.test_data_path / Path("local_index")
    for file_path in bib_files_to_index.glob("**/*"):
        local_index_test_records_dict[Path(file_path.name)] = {}

    for path in local_index_test_records_dict:
        with open(bib_files_to_index.joinpath(path), encoding="utf-8") as file:
            parser = bibtex.Parser()
            bib_data = parser.parse_string(file.read())
            loaded_records = colrev.dataset.Dataset.parse_records_dict(
                records_dict=bib_data.entries
            )
            # Note : we only select one example for the TEI-indexing
            for loaded_record in loaded_records.values():
                if "file" not in loaded_record:
                    continue

                if loaded_record["ID"] != "WagnerLukyanenkoParEtAl2022":
                    del loaded_record["file"]
                else:
                    loaded_record["file"] = str(
                        test_local_index_dir / Path(loaded_record["file"])
                    )

            local_index_test_records_dict[path] = loaded_records

    return local_index_test_records_dict


@pytest.fixture(scope="session")
def local_index(session_mocker, helpers, local_index_test_records_dict, test_local_index_dir):  # type: ignore
    """Test the local_index"""
    helpers.retrieve_test_file(
        source=Path("WagnerLukyanenkoParEtAl2022.pdf"),
        target=test_local_index_dir / Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"),
    )
    helpers.retrieve_test_file(
        source=Path("WagnerLukyanenkoParEtAl2022.tei.xml"),
        target=test_local_index_dir
        / Path("data/.tei/WagnerLukyanenkoParEtAl2022.tei.xml"),
    )

    os.chdir(test_local_index_dir)
    temp_sqlite = test_local_index_dir / Path("sqlite_index_test.db")
    session_mocker.patch.object(
        colrev.env.local_index.LocalIndex, "SQLITE_PATH", temp_sqlite
    )
    local_index_instance = colrev.env.local_index.LocalIndex(
        index_tei=True, verbose_mode=True
    )
    local_index_instance.reinitialize_sqlite_db()

    for path, records in local_index_test_records_dict.items():
        if "cura" in str(path):
            continue
        local_index_instance.index_records(
            records=records,
            repo_source_path=path,
            curated_fields=[],
            curation_url="gh...",
            curated_masterdata=True,
        )

    for path, records in local_index_test_records_dict.items():
        if "cura" not in str(path):
            continue
        local_index_instance.index_records(
            records=records,
            repo_source_path=path,
            curated_fields=["literature_review"],
            curation_url="gh...",
            curated_masterdata=False,
        )

    return local_index_instance
