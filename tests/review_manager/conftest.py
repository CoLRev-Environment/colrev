#!/usr/bin/env python
"""Conftest file containing fixtures to set up tests efficiently"""
from __future__ import annotations

import os
import typing
import warnings
from pathlib import Path

import git
import pytest

import colrev.env.local_index
import colrev.env.local_index_builder
import colrev.exceptions as colrev_exceptions
import colrev.ops.init
import colrev.record.record_pdf
import colrev.review_manager
from colrev import utils
from colrev.constants import Colors
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchType
from colrev.process.model import ProcessModel

# Note : the following produces different relative paths locally/on github.
# Path(colrev.__file__).parents[1]

# pylint: disable=line-too-long


# pylint: disable=too-few-public-methods
class ReviewManagerHelpers:
    """Helpers class providing utility functions (e.g., for test-file retrieval)"""

    @staticmethod
    def reset_commit(
        review_manager: colrev.review_manager.ReviewManager,
        *,
        commit: str = "",
        commit_sha: str = "",
    ) -> None:
        """Reset to the selected commit"""
        assert commit == "" or commit_sha == ""
        print(f"Resetting to commit {commit} {commit_sha}")
        os.chdir(str(review_manager.path))
        repo = git.Repo(review_manager.path)
        if commit_sha != "":
            commit_id = commit_sha
        elif commit:
            commit_id = getattr(review_manager, commit)
        repo.head.reset(commit_id, index=True, working_tree=True)

        # To prevent prep from continuing previous operations
        Path(".colrev/cur_temp_recs.bib").unlink(missing_ok=True)
        Path(".colrev/temp_recs.bib").unlink(missing_ok=True)
        review_manager.load_settings()


@pytest.fixture(scope="session", name="review_manager_helpers")
def get_helpers():  # type: ignore
    """Fixture returning ReviewManagerHelpers"""
    return ReviewManagerHelpers


@pytest.fixture(autouse=True)
def run_around_tests(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> typing.Generator:
    """Fixture to clean up after tests"""

    # pre-test-code
    # ...

    yield  # run test-code

    # post-test-code
    print(
        "Post-test teardown: Restore repository state (in colrev/tests/review_manager/conftest.py)"
    )
    os.chdir(str(base_repo_review_manager.path))
    base_repo_review_manager.load_settings()
    base_repo_review_manager.notified_next_operation = None
    repo = git.Repo(base_repo_review_manager.path)
    repo.git.clean("-df")
    review_manager_helpers.reset_commit(base_repo_review_manager, commit="data_commit")


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

    test_repo_dir = tmp_path_factory.mktemp("base_repo")  # type: ignore

    session_mocker.patch.object(
        colrev.constants.Filepaths,
        "REGISTRY_FILE",
        test_repo_dir / "reg.json",
    )
    os.chdir(test_repo_dir)
    colrev.ops.init.Initializer(
        review_type="literature_review",
        target_path=test_repo_dir,
        light=True,
    )

    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir),
    )

    review_manager.get_load_operation()
    git_repo = review_manager.dataset.git_repo.repo
    if utils.in_ci_environment():
        git_repo.config_writer().set_value("user", "name", "Tester").release()
        git_repo.config_writer().set_value("user", "email", "tester@mail.com").release()

    def load_test_records(test_data_path) -> dict:  # type: ignore
        test_records_dict: typing.Dict[Path, dict] = {}
        bib_files_to_index = test_data_path / Path("data/local_index")
        for file_path in bib_files_to_index.glob("**/*"):
            test_records_dict[Path(file_path.name)] = {}

        for path in test_records_dict:
            test_records_dict[path] = colrev.loader.load_utils.load(
                filename=bib_files_to_index.joinpath(path),
                logger=review_manager.logger,
                unique_id_field="ID",
            )

        return test_records_dict

    temp_sqlite = review_manager.path.parent / Path("sqlite_index_test.db")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with session_mocker.patch.object(
            colrev.constants.Filepaths, "LOCAL_INDEX_SQLITE_FILE", temp_sqlite
        ):
            test_records_dict = load_test_records(helpers.test_data_path)
            local_index_builder = colrev.env.local_index_builder.LocalIndexBuilder(
                verbose_mode=True
            )
            local_index_builder.reinitialize_sqlite_db()

            for path, records in test_records_dict.items():
                if "cura" in str(path):
                    continue
                local_index_builder.index_records(
                    records=records,
                    repo_source_path=path,
                    curated_fields=[],
                    curation_url="gh...",
                    curated_masterdata=True,
                )

            for path, records in test_records_dict.items():
                if "cura" not in str(path):
                    continue
                local_index_builder.index_records(
                    records=records,
                    repo_source_path=path,
                    curated_fields=["literature_review"],
                    curation_url="gh...",
                    curated_masterdata=False,
                )

    dedupe_operation = review_manager.get_dedupe_operation()
    dedupe_operation.review_manager.settings.project.delay_automated_processing = True
    with pytest.raises(colrev_exceptions.NoRecordsError):
        ProcessModel.check_operation_precondition(dedupe_operation)
    dedupe_operation.review_manager.settings.project.delay_automated_processing = False

    review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev.source_specific_prep"},
    ]
    review_manager.settings.dedupe.dedupe_package_endpoints = [
        {"endpoint": "colrev.dedupe"}
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
        review_manager.dataset.git_repo.get_last_commit_sha()
    )

    helpers.retrieve_test_file(
        source=Path("data/search_files/test_records.bib"),
        target=Path("data/search/test_records.bib"),
    )
    review_manager.dataset.git_repo.add_changes(Path("data/search/test_records.bib"))
    test_bib_source = colrev.search_file.ExtendedSearchFile(
        platform="colrev.unknown_source",
        search_results_path=Path("data/search/test_records.bib"),
        search_type=SearchType.DB,
        search_string="",
        comment="",
        version="0.1.0",
    )
    review_manager.settings.sources = [test_bib_source]
    # TODO : should the saving be done by settings.save()?
    search_history_file_path = Path("data/search/test_records_search_history.json")
    test_bib_source.save(search_history_file_path)
    review_manager.dataset.git_repo.add_changes(search_history_file_path)
    review_manager.load_settings()
    review_manager.create_commit(msg="add test_records.bib", manual_author=True)
    review_manager.add_test_records_commit = (
        review_manager.dataset.git_repo.get_last_commit_sha()
    )

    search_operation = review_manager.get_search_operation()
    search_operation.add_most_likely_sources()

    load_operation = review_manager.get_load_operation()
    load_operation.main(keep_ids=False)
    review_manager.load_commit = review_manager.dataset.git_repo.get_last_commit_sha()

    prep_operation = review_manager.get_prep_operation()
    prep_operation.main(keep_ids=True)
    review_manager.prep_commit = review_manager.dataset.git_repo.get_last_commit_sha()

    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.main()
    review_manager.dedupe_commit = review_manager.dataset.git_repo.get_last_commit_sha()

    prescreen_operation = review_manager.get_prescreen_operation()
    prescreen_operation.main(split_str="NA")
    review_manager.prescreen_commit = (
        review_manager.dataset.git_repo.get_last_commit_sha()
    )

    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.main()
    review_manager.pdf_get_commit = (
        review_manager.dataset.git_repo.get_last_commit_sha()
    )

    pdf_prep_operation = review_manager.get_pdf_prep_operation(reprocess=False)
    pdf_prep_operation.main(batch_size=0)
    review_manager.pdf_prep_commit = (
        review_manager.dataset.git_repo.get_last_commit_sha()
    )

    screen_operation = review_manager.get_screen_operation()
    screen_operation.main(split_str="NA")
    review_manager.screen_commit = review_manager.dataset.git_repo.get_last_commit_sha()

    data_operation = review_manager.get_data_operation()
    data_operation.main()
    review_manager.create_commit(msg="Data and synthesis", manual_author=True)
    review_manager.data_commit = review_manager.dataset.git_repo.get_last_commit_sha()
    review_manager.logger.info(
        f"{Colors.RED}Test repository in {test_repo_dir}{Colors.END}"
    )

    return review_manager


@pytest.fixture(scope="session", name="quality_model")
def fixture_quality_model(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> colrev.record.qm.quality_model.QualityModel:
    """Fixture returning the quality model"""
    return base_repo_review_manager.get_qm()


@pytest.fixture(scope="session", name="pdf_quality_model")
def fixture_pdf_quality_model(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> colrev.record.qm.quality_model.QualityModel:
    """Fixture returning the pdf quality model"""

    helpers.retrieve_test_file(
        source=Path("data/WagnerLukyanenkoParEtAl2022.pdf"),
        target=base_repo_review_manager.path
        / Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"),
    )
    return base_repo_review_manager.get_pdf_qm()


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


@pytest.fixture(scope="package", name="dedupe_operation")
def fixture_pdedupe_operation(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> colrev.ops.dedupe.Dedupe:
    """Fixture returning a dedupe operation"""
    return base_repo_review_manager.get_dedupe_operation()


@pytest.fixture
def record_with_pdf(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> colrev.record.record.Record:
    """Fixture returning a record containing a file (PDF)"""
    return colrev.record.record_pdf.PDFRecord(
        {
            Fields.ID: "WagnerLukyanenkoParEtAl2022",
            Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
            Fields.FILE: Path("data/pdfs/WagnerLukyanenkoParEtAl2022.pdf"),
        },
        path=base_repo_review_manager.path,
    )


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


@pytest.fixture(name="v_t_pdf_record")
def fixture_v_t_pdf_record(
    v_t_record: colrev.record.record.Record,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> colrev.record.record_pdf.PDFRecord:
    """Record for testing quality defects"""
    return colrev.record.record_pdf.PDFRecord(
        v_t_record.data, path=base_repo_review_manager.path
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
