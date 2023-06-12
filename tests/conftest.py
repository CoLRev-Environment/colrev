#!/usr/bin/env python
"""Conftest file containing fixtures to set up tests efficiently"""
from __future__ import annotations

import os
import shutil
import typing
from pathlib import Path

import git
import pytest
from pybtex.database.input import bibtex

import colrev.env.local_index
import colrev.exceptions as colrev_exceptions
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

    @staticmethod
    def retrieve_test_file_content(*, source: Path) -> str:
        """Retrieve the content of a test file"""
        return (Helpers.test_data_path / source).read_text(encoding="utf-8")

    @staticmethod
    def reset_commit(
        *, review_manager: colrev.review_manager.ReviewManager, commit: str
    ) -> None:
        """Reset to the selected commit"""
        os.chdir(str(review_manager.path))
        repo = git.Repo(review_manager.path)
        commit_id = getattr(review_manager, commit)
        repo.head.reset(commit_id, index=True, working_tree=True)


@pytest.fixture(scope="session", name="helpers")
def get_helpers():  # type: ignore
    """Fixture returning Helpers"""
    return Helpers


@pytest.fixture(scope="session", name="test_local_index_dir")
def get_test_local_index_dir(tmp_path_factory):  # type: ignore
    """Fixture returning the test_local_index_dir"""
    return tmp_path_factory.mktemp("local_index")


@pytest.fixture(scope="session", name="base_repo_review_manager")
def fixture_base_repo_review_manager(session_mocker, tmp_path_factory, helpers):  # type: ignore
    """Fixture returning the base review_manager"""
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements

    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.register_repo",
        return_value=(),
    )

    test_repo_dir = tmp_path_factory.mktemp("base_repo")  # type: ignore

    session_mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "registry_yaml",
        test_repo_dir / "reg.yaml",
    )
    session_mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "registry",
        test_repo_dir / "reg.json",
    )
    os.chdir(test_repo_dir)
    colrev.review_manager.get_init_operation(
        review_type="literature_review",
        target_path=test_repo_dir,
        light=True,
    )
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )

    review_manager.get_load_operation()
    git_repo = review_manager.dataset.get_repo()
    if review_manager.in_ci_environment():
        git_repo.config_writer().set_value("user", "name", "Tester").release()
        git_repo.config_writer().set_value("user", "email", "tester@mail.com").release()

    def load_test_records(test_data_path) -> dict:  # type: ignore
        test_records_dict: typing.Dict[Path, dict] = {}
        bib_files_to_index = test_data_path / Path("local_index")
        for file_path in bib_files_to_index.glob("**/*"):
            test_records_dict[Path(file_path.name)] = {}

        for path in test_records_dict:
            with open(bib_files_to_index.joinpath(path), encoding="utf-8") as file:
                parser = bibtex.Parser()
                bib_data = parser.parse_string(file.read())
                test_records_dict[path] = colrev.dataset.Dataset.parse_records_dict(
                    records_dict=bib_data.entries
                )
        return test_records_dict

    temp_sqlite = review_manager.path.parent / Path("sqlite_index_test.db")
    with session_mocker.patch.object(
        colrev.env.local_index.LocalIndex, "SQLITE_PATH", temp_sqlite
    ):
        test_records_dict = load_test_records(helpers.test_data_path)
        local_index = colrev.env.local_index.LocalIndex(verbose_mode=True)
        local_index.reinitialize_sqlite_db()

        for path, records in test_records_dict.items():
            if "cura" in str(path):
                continue
            local_index.index_records(
                records=records,
                repo_source_path=path,
                curated_fields=[],
                curation_url="gh...",
                curated_masterdata=True,
            )

        for path, records in test_records_dict.items():
            if "cura" not in str(path):
                continue
            local_index.index_records(
                records=records,
                repo_source_path=path,
                curated_fields=["literature_review"],
                curation_url="gh...",
                curated_masterdata=False,
            )

    dedupe_operation = review_manager.get_dedupe_operation()
    dedupe_operation.review_manager.settings.project.delay_automated_processing = True
    with pytest.raises(colrev_exceptions.NoRecordsError):
        colrev.record.RecordStateModel.check_operation_precondition(
            operation=dedupe_operation
        )
    dedupe_operation.review_manager.settings.project.delay_automated_processing = False

    review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev.resolve_crossrefs"},
        {"endpoint": "colrev.source_specific_prep"},
        # {"endpoint": "colrev.exclude_non_latin_alphabets"},
        # {"endpoint": "colrev.exclude_collections"},
    ]
    review_manager.settings.dedupe.dedupe_package_endpoints = [
        {"endpoint": "colrev.simple_dedupe"}
    ]
    review_manager.settings.prescreen.prescreen_package_endpoints = [
        {"endpoint": "colrev.conditional_prescreen"}
    ]

    review_manager.settings.pdf_get.pdf_get_package_endpoints = [
        {"endpoint": "colrev.local_index"}
    ]
    review_manager.settings.pdf_prep.pdf_prep_package_endpoints = []
    review_manager.settings.screen.screen_package_endpoints = []
    review_manager.settings.data.data_package_endpoints = []
    review_manager.save_settings()
    review_manager.create_commit(msg="change settings", manual_author=True)
    review_manager.changed_settings_commit = (
        review_manager.dataset.get_last_commit_sha()
    )

    helpers.retrieve_test_file(
        source=Path("search_files/test_records.bib"),
        target=Path("data/search/test_records.bib"),
    )
    review_manager.dataset.add_changes(path=Path("data/search/test_records.bib"))
    review_manager.create_commit(msg="add test_records.bib", manual_author=True)
    review_manager.add_test_records_commit = (
        review_manager.dataset.get_last_commit_sha()
    )

    load_operation = review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources, keep_ids=False, combine_commits=False)
    review_manager.load_commit = review_manager.dataset.get_last_commit_sha()

    prep_operation = review_manager.get_prep_operation()
    prep_operation.main(keep_ids=False)
    review_manager.prep_commit = review_manager.dataset.get_last_commit_sha()

    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.main()
    review_manager.dedupe_commit = review_manager.dataset.get_last_commit_sha()

    prescreen_operation = review_manager.get_prescreen_operation()
    prescreen_operation.main(split_str="NA")
    review_manager.prescreen_commit = review_manager.dataset.get_last_commit_sha()

    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.main()
    review_manager.pdf_get_commit = review_manager.dataset.get_last_commit_sha()

    pdf_prep_operation = review_manager.get_pdf_prep_operation(reprocess=False)
    pdf_prep_operation.main(batch_size=0)
    review_manager.pdf_prep_commit = review_manager.dataset.get_last_commit_sha()

    screen_operation = review_manager.get_screen_operation()
    screen_operation.main(split_str="NA")
    review_manager.screen_commit = review_manager.dataset.get_last_commit_sha()

    data_operation = review_manager.get_data_operation()
    data_operation.main()
    review_manager.create_commit(msg="Data and synthesis", manual_author=True)
    review_manager.data_commit = review_manager.dataset.get_last_commit_sha()

    return review_manager


@pytest.fixture(scope="session", name="quality_model")
def fixture_quality_model(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> colrev.qm.quality_model.QualityModel:
    """Fixture returning the quality model"""
    return base_repo_review_manager.get_qm()


@pytest.fixture(scope="module")
def language_service() -> colrev.env.language_service.LanguageService:  # type: ignore
    """Return a language service object"""

    return colrev.env.language_service.LanguageService()


@pytest.fixture(scope="package", name="prep_operation")
def fixture_prep_operation(
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
def get_local_index_test_records_dict(  # type: ignore
    helpers,
    test_local_index_dir,
) -> dict:
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


@pytest.fixture(scope="session", name="local_index")
def get_local_index(  # type: ignore
    session_mocker, helpers, local_index_test_records_dict, test_local_index_dir
):
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


@pytest.fixture(scope="module")
def script_loc(request) -> Path:  # type: ignore
    """Return the directory of the currently running test script"""

    return Path(request.fspath).parent


@pytest.fixture(scope="function", name="_patch_registry")
def patch_registry(mocker, tmp_path) -> None:  # type: ignore
    """Patch registry path in environment manager"""
    test_json_path = tmp_path / Path("reg.json")
    test_yaml_path = tmp_path / Path("reg.yaml")

    mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "registry_yaml",
        test_yaml_path,
    )
    mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "registry",
        test_json_path,
    )


@pytest.fixture(name="v_t_record")
def fixture_v_t_record() -> colrev.record.Record:
    """Record for testing quality defects"""
    return colrev.record.Record(
        data={
            "ID": "WagnerLukyanenkoParEtAl2022",
            "ENTRYTYPE": "article",
            "file": Path("WagnerLukyanenkoParEtAl2022.pdf"),
            "journal": "Journal of Information Technology",
            "author": "Wagner, Gerit and Lukyanenko, Roman and Paré, Guy",
            "title": "Artificial intelligence and the conduct of literature reviews",
            "year": "2022",
            "volume": "37",
            "number": "2",
        }
    )
