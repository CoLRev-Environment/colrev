#!/usr/bin/env python
"""Conftest file containing fixtures to set up tests efficiently"""
from __future__ import annotations

import os
import shutil
import typing
from pathlib import Path

import pytest

import colrev.env.local_index
import colrev.env.local_index_builder
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

# Note : the following produces different relative paths locally/on github.
# Path(colrev.__file__).parents[1]

# pylint: disable=line-too-long


# pylint: disable=too-few-public-methods
class Helpers:
    """Helpers class providing utility functions (e.g., for test-file retrieval)"""

    test_data_path = Path(__file__).parent

    @staticmethod
    def retrieve_test_file(*, source: Path, target: Path) -> None:
        """Retrieve a test file"""
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy(
            Helpers.test_data_path / source,
            target,
        )

    @staticmethod
    def retrieve_test_file_content(*, source: Path) -> str:
        """Retrieve the content of a test file"""
        return (Helpers.test_data_path / source).read_text(encoding="utf-8")


@pytest.fixture(scope="session", name="helpers")
def get_helpers():  # type: ignore
    """Fixture returning Helpers"""
    return Helpers


@pytest.fixture(scope="session", name="test_local_index_dir")
def get_test_local_index_dir(tmp_path_factory):  # type: ignore
    """Fixture returning the test_local_index_dir"""
    return tmp_path_factory.mktemp("local_index")


@pytest.fixture(scope="module")
def language_service() -> colrev.env.language_service.LanguageService:  # type: ignore
    """Return a language service object"""

    return colrev.env.language_service.LanguageService()


@pytest.fixture(scope="session", name="local_index_test_records_dict")
def get_local_index_test_records_dict(  # type: ignore
    helpers,
    test_local_index_dir,
) -> dict:
    """Test records dict for local_index"""
    local_index_test_records_dict: typing.Dict[Path, dict] = {}
    bib_files_to_index = helpers.test_data_path / Path("data/local_index")
    for file_path in bib_files_to_index.glob("**/*"):
        local_index_test_records_dict[Path(file_path.name)] = {}

    for path in local_index_test_records_dict:
        loaded_records = colrev.loader.load_utils.load(
            filename=bib_files_to_index.joinpath(path),
            unique_id_field="ID",
        )

        # Note : we only select one example for the TEI-indexing
        for loaded_record in loaded_records.values():
            if Fields.FILE not in loaded_record:
                continue

            if loaded_record[Fields.ID] != "WagnerLukyanenkoParEtAl2022":
                del loaded_record[Fields.FILE]
            else:
                loaded_record[Fields.FILE] = str(
                    test_local_index_dir / Path(loaded_record[Fields.FILE])
                )

        local_index_test_records_dict[path] = loaded_records

    return local_index_test_records_dict


@pytest.fixture(scope="session", name="local_index")
def get_local_index(  # type: ignore
    session_mocker, helpers, local_index_test_records_dict, test_local_index_dir
):
    """Test the local_index"""
    target_pdf_path = test_local_index_dir / Path(
        "data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"
    )
    target_pdf_path.parent.mkdir(exist_ok=True, parents=True)
    helpers.retrieve_test_file(
        source=Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
        target=target_pdf_path,
    )
    target_tei_path = test_local_index_dir / Path(
        "data/.tei/WagnerLukyanenkoParEtAl2022.tei.xml"
    )
    target_tei_path.parent.mkdir(exist_ok=True, parents=True)
    helpers.retrieve_test_file(
        source=Path("data/WagnerLukyanenkoParEtAl2022.tei.xml"),
        target=target_tei_path,
    )

    os.chdir(test_local_index_dir)
    temp_sqlite = test_local_index_dir / Path("sqlite_index_test.db")
    session_mocker.patch.object(
        colrev.constants.Filepaths, "LOCAL_INDEX_SQLITE_FILE", temp_sqlite
    )
    local_index_builder = colrev.env.local_index_builder.LocalIndexBuilder(
        index_tei=True, verbose_mode=True
    )
    local_index_builder.reinitialize_sqlite_db()

    for path, records in local_index_test_records_dict.items():
        if "cura" in str(path):
            continue
        local_index_builder.index_records(
            records=records,
            repo_source_path=path,
            curated_fields=[],
            curation_url="gh...",
            curated_masterdata=True,
        )

    for path, records in local_index_test_records_dict.items():
        if "cura" not in str(path):
            continue
        local_index_builder.index_records(
            records=records,
            repo_source_path=path,
            curated_fields=["literature_review"],
            curation_url="gh...",
            curated_masterdata=False,
        )

    local_index = colrev.env.local_index.LocalIndex()

    return local_index


@pytest.fixture(scope="module")
def script_loc(request) -> Path:  # type: ignore
    """Return the directory of the currently running test script"""

    return Path(request.fspath).parent


@pytest.fixture(scope="function", name="_patch_registry")
def patch_registry(mocker, tmp_path) -> None:  # type: ignore
    """Patch registry path in environment manager"""
    test_json_path = tmp_path / Path("reg.json")

    mocker.patch.object(
        colrev.constants.Filepaths,
        "REGISTRY_FILE",
        test_json_path,
    )


@pytest.fixture(name="v_t_record")
def fixture_v_t_record() -> colrev.record.record.Record:
    """Record for testing quality defects"""
    return colrev.record.record.Record(
        {
            Fields.ID: "WagnerLukyanenkoParEtAl2022",
            Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
            Fields.FILE: Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"),
            Fields.JOURNAL: "Journal of Information Technology",
            Fields.AUTHOR: "Wagner, Gerit and Lukyanenko, Roman and Paré, Guy",
            Fields.TITLE: "Artificial intelligence and the conduct of literature reviews",
            Fields.YEAR: "2022",
            Fields.VOLUME: "37",
            Fields.NUMBER: "2",
            Fields.LANGUAGE: "eng",
        }
    )


@pytest.fixture(name="book_record")
def fixture_book_record() -> colrev.record.record.Record:
    """Book record for testing quality defects"""
    return colrev.record.record.Record(
        {
            Fields.ID: "Popper2014",
            Fields.ENTRYTYPE: ENTRYTYPES.BOOK,
            Fields.TITLE: "Conjectures and refutations: The growth of scientific knowledge",
            Fields.AUTHOR: "Popper, Karl",
            Fields.YEAR: "2014",
            Fields.ISBN: "978-0-415-28594-0",
            Fields.PUBLISHER: "Routledge",
            Fields.LANGUAGE: "eng",
        }
    )
