#!/usr/bin/env python
"""Tests of the CoLRev operations"""
import os
import platform
import shutil
from dataclasses import asdict
from pathlib import Path

import git
import pytest

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.review_manager
import colrev.settings

# pylint: disable=line-too-long


@pytest.fixture(scope="module", name="ops_test_review_manager")
def fixture_ops_test_review_manager(  # type: ignore
    session_mocker, tmp_path_factory: Path, helpers
) -> colrev.review_manager.ReviewManager:
    """Fixture setting up the review_manager"""

    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.register_repo",
        return_value=(),
    )

    test_repo_dir = tmp_path_factory.mktemp("test_repo")  # type: ignore
    os.chdir(test_repo_dir)
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    review_manager.settings = colrev.settings.load_settings(
        settings_path=helpers.test_data_path.parents[1]
        / Path("colrev/template/init/settings.json")
    )

    colrev.review_manager.get_init_operation(
        review_type="literature_review", example=False, target_path=test_repo_dir
    )

    # Note: the strategy is to test the workflow and the endpoints separately
    # We therefore deactivate the (most time consuming endpoints) in the following
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(review_manager.path)
    )

    dedupe_operation = review_manager.get_dedupe_operation()
    dedupe_operation.review_manager.settings.project.delay_automated_processing = True
    with pytest.raises(colrev_exceptions.NoRecordsError):
        colrev.record.RecordStateModel.check_operation_precondition(
            operation=dedupe_operation
        )
    dedupe_operation.review_manager.settings.project.delay_automated_processing = False

    helpers.retrieve_test_file(
        source=Path("search_files/test_records.bib"),
        target=Path("data/search/test_records.bib"),
    )

    review_manager.dataset.add_changes(path=Path("data/search/test_records.bib"))
    review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev.resolve_crossrefs"},
        {"endpoint": "colrev.source_specific_prep"},
        {"endpoint": "colrev.exclude_non_latin_alphabets"},
        {"endpoint": "colrev.exclude_collections"},
    ]
    review_manager.settings.dedupe.dedupe_package_endpoints = [
        {"endpoint": "colrev.simple_dedupe"}
    ]

    review_manager.settings.pdf_get.pdf_get_package_endpoints = [
        {"endpoint": "colrev.local_index"}
    ]
    review_manager.settings.pdf_prep.pdf_prep_package_endpoints = []
    review_manager.settings.data.data_package_endpoints = []
    review_manager.save_settings()
    review_manager.create_commit(msg="add test_records.bib", manual_author=True)
    return review_manager


def local_pdf_collection(helpers, tmp_path_factory):  # type: ignore
    """Test the local_pdf_collection setup"""
    test_repo_dir = tmp_path_factory.mktemp("test_repo_local_pdf_collection")  # type: ignore
    os.chdir(test_repo_dir)
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    review_manager.settings = colrev.settings.load_settings(
        settings_path=helpers.test_data_path.parents[1]
        / Path("colrev/template/init/settings.json")
    )

    review_manager = colrev.review_manager.get_init_operation(
        review_type="curated_masterdata",
        example=False,
        local_pdf_collection=True,
    )


def test_repo_init_error(tmp_path) -> None:  # type: ignore
    """Test repo init error (non-empty dir)"""
    colrev.review_manager.ReviewManager.REPORT_RELATIVE.write_text(
        "test", encoding="utf-8"
    )
    # colrev status/etc. should print the RepoSetupError in non-colrev repositories
    with pytest.raises(colrev_exceptions.RepoSetupError):
        colrev.review_manager.ReviewManager(path_str=str(tmp_path), force_mode=False)


def test_repo_init_errors(tmp_path, helpers) -> None:  # type: ignore
    """Test repo init error (non-empty dir)"""

    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(tmp_path), force_mode=True
    )
    review_manager.settings = colrev.settings.load_settings(
        settings_path=helpers.test_data_path.parents[1]
        / Path("colrev/template/init/settings.json")
    )

    with pytest.raises(colrev_exceptions.RepoInitError):
        colrev.review_manager.get_init_operation(
            review_type="literature_review",
            example=True,
            local_pdf_collection=True,
            target_path=tmp_path,
        )

    with pytest.raises(colrev_exceptions.ParameterError):
        colrev.review_manager.get_init_operation(
            review_type="misspelled_review", target_path=tmp_path
        )

    colrev.review_manager.get_init_operation(
        review_type="literature_review",
        example=True,
        target_path=tmp_path,
        light=True,
    )


def test_non_empty_dir_error_init(tmp_path) -> None:  # type: ignore
    """Test repo init error (non-empty dir)"""
    # A .report.log file that should be removed
    (tmp_path / colrev.review_manager.ReviewManager.REPORT_RELATIVE).write_text(
        "test", encoding="utf-8"
    )
    (tmp_path / Path("test.txt")).write_text("test", encoding="utf-8")
    with pytest.raises(colrev_exceptions.NonEmptyDirectoryError):
        colrev.review_manager.get_init_operation(
            review_type="literature_review", example=False, target_path=tmp_path
        )
    Path("test.txt").unlink()


def test_load(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the load operation"""
    load_operation = ops_test_review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources, keep_ids=False, combine_commits=False)


def test_check_operation_precondition(
    ops_test_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the check operation preconditions"""
    dedupe_operation = ops_test_review_manager.get_dedupe_operation()
    dedupe_operation.review_manager.settings.project.delay_automated_processing = True
    with pytest.raises(colrev_exceptions.ProcessOrderViolation):
        colrev.record.RecordStateModel.check_operation_precondition(
            operation=dedupe_operation
        )
    dedupe_operation.review_manager.settings.project.delay_automated_processing = False


def test_load_pubmed(  # type: ignore
    ops_test_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test loading a pubmed file"""

    current_commit = ops_test_review_manager.dataset.get_last_commit_sha()

    pubmed_file = helpers.test_data_path / Path("search_files/pubmed-chatbot.csv")
    shutil.copy(
        pubmed_file,
        ops_test_review_manager.path / Path("data/search/pubmed-chatbot.csv"),
    )
    load_operation = ops_test_review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    new_sources[0].endpoint = "colrev.pubmed"
    load_operation.main(new_sources=new_sources, keep_ids=False, combine_commits=False)

    expected = (
        helpers.test_data_path / Path("search_files/pubmed-chatbot-expected.bib")
    ).read_text()
    actual = (
        ops_test_review_manager.path / Path("data/search/pubmed-chatbot.bib")
    ).read_text()
    assert expected == actual

    repo = git.Repo(ops_test_review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)

    ops_test_review_manager.load_settings()


def test_prep(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the prep operation"""

    prep_operation = ops_test_review_manager.get_prep_operation()
    current_commit = ops_test_review_manager.dataset.get_last_commit_sha()
    prep_operation.skip_prep()
    repo = git.Repo(ops_test_review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)

    prep_operation.main(keep_ids=False)

    current_commit = ops_test_review_manager.dataset.get_last_commit_sha()

    prep_operation.set_ids()
    # TODO : difference set_ids - reset_ids?
    prep_operation.setup_custom_script()
    prep_operation.reset_ids()

    repo = git.Repo(ops_test_review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)


def test_prep_man(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the prep-man operation"""

    prep_man_operation = ops_test_review_manager.get_prep_man_operation()
    prep_man_operation.prep_man_stats()
    prep_man_operation.main()


def test_search(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the search operation"""

    search_operation = ops_test_review_manager.get_search_operation()
    search_operation.main(rerun=True)

    search_operation.view_sources()


def test_search_get_unique_filename(
    ops_test_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the search.get_unique_filename()"""

    search_operation = ops_test_review_manager.get_search_operation()
    expected = Path("data/search/test_records_1.bib")
    actual = search_operation.get_unique_filename(file_path_string="test_records.bib")
    print(actual)
    assert expected == actual


def test_dedupe(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the dedupe operation"""
    dedupe_operation = ops_test_review_manager.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.main()


def test_prescreen(
    ops_test_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the prescreen operation"""

    prescreen_operation = ops_test_review_manager.get_prescreen_operation()
    prescreen_operation.create_prescreen_split(create_split=2)
    ops_test_review_manager.settings.prescreen.prescreen_package_endpoints = [
        {"endpoint": "colrev.conditional_prescreen"}
    ]
    prescreen_operation.main(split_str="NA")
    prescreen_operation.include_all_in_prescreen(persist=False)

    current_commit = ops_test_review_manager.dataset.get_last_commit_sha()
    prescreen_operation.setup_custom_script()
    repo = git.Repo(ops_test_review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)


def test_pdf_get(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the pdf-get operation"""

    pdf_get_operation = ops_test_review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.main()


def test_pdf_prep(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the pdf-prep operation"""

    pdf_prep_operation = ops_test_review_manager.get_pdf_prep_operation(reprocess=False)
    pdf_prep_operation.main(batch_size=0)


def test_pdf_discard(
    ops_test_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the pdfs --discard"""

    pdf_get_man_operation = ops_test_review_manager.get_pdf_get_man_operation()
    pdf_get_man_operation.discard()


def test_pdf_prep_man(
    ops_test_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the pdf-prep-man operation"""

    pdf_prep_man_operation = ops_test_review_manager.get_pdf_prep_man_operation()
    pdf_prep_man_operation.main()
    pdf_prep_man_operation.pdf_prep_man_stats()
    pdf_prep_man_operation.extract_needs_pdf_prep_man()
    pdf_prep_man_operation.discard()


def test_screen(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the screen operation"""

    screen_operation = ops_test_review_manager.get_screen_operation()
    ops_test_review_manager.settings.screen.screen_package_endpoints = []
    screen_operation.main(split_str="NA")
    screen_operation.include_all_in_screen(persist=False)
    screen_operation.create_screen_split(create_split=2)

    current_commit = ops_test_review_manager.dataset.get_last_commit_sha()
    screen_operation.setup_custom_script()
    repo = git.Repo(ops_test_review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)


def test_data(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the date operation"""

    data_operation = ops_test_review_manager.get_data_operation()
    data_operation.main()
    ops_test_review_manager.create_commit(msg="Data and synthesis", manual_author=True)
    data_operation.profile()

    current_commit = ops_test_review_manager.dataset.get_last_commit_sha()
    data_operation.setup_custom_script()
    repo = git.Repo(ops_test_review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)

    ops_test_review_manager.load_settings()


def test_checks(ops_test_review_manager: colrev.review_manager.ReviewManager) -> None:
    """Test the checks"""

    checker = colrev.checker.Checker(review_manager=ops_test_review_manager)

    expected = ["0.8.3", "0.8.3"]
    actual = checker.get_colrev_versions()
    assert expected == actual

    checker.check_repository_setup()

    # Note: no assertion (yet)
    checker.in_virtualenv()

    actual = checker.check_repo_extended()
    current_platform = platform.system()
    expected = []
    assert expected == actual

    actual = checker.check_repo()  # type: ignore

    expected = {"status": 0, "msg": "Everything ok."}  # type: ignore
    assert expected == actual

    expected = []
    actual = checker.check_repo_basics()
    assert expected == actual

    if current_platform in ["Linux"]:
        expected = []
        actual = checker.check_change_in_propagated_id(
            prior_id="Srivastava2015",
            new_id="Srivastava2015a",
            project_context=ops_test_review_manager.path,
        )
        assert expected == actual

    ops_test_review_manager.get_search_sources()
    search_sources = ops_test_review_manager.settings.sources
    actual = [asdict(s) for s in search_sources]  # type: ignore

    if current_platform in ["Linux"]:
        expected = [  # type: ignore
            {  # type: ignore
                "endpoint": "colrev.pdfs_dir",
                "filename": Path("data/search/pdfs.bib"),
                "search_type": colrev.settings.SearchType.PDFS,
                "search_parameters": {"scope": {"path": "data/pdfs"}},
                "load_conversion_package_endpoint": {"endpoint": "colrev.bibtex"},
                "comment": "",
            },
            {  # type: ignore
                "endpoint": "colrev.unknown_source",
                "filename": Path("data/search/test_records.bib"),
                "search_type": colrev.settings.SearchType.DB,
                "search_parameters": {},
                "load_conversion_package_endpoint": {"endpoint": "colrev.bibtex"},
                "comment": None,
            },
        ]
        assert expected == actual
    elif current_platform in ["Darwin"]:
        expected = [  # type: ignore
            {  # type: ignore
                "endpoint": "colrev.unknown_source",
                "filename": Path("data/search/test_records.bib"),
                "search_type": colrev.settings.SearchType.DB,
                "search_parameters": {},
                "load_conversion_package_endpoint": {"endpoint": "colrev.bibtex"},
                "comment": None,
            },
        ]
        assert expected == actual
