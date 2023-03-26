#!/usr/bin/env python
import os
import shutil
import typing
from dataclasses import asdict
from pathlib import Path

import git
import pytest
from pybtex.database.input import bibtex

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.review_manager
import colrev.settings

# Note : the following produces different relative paths locally/on github.
# Path(colrev.__file__).parents[1]

test_data_path = Path()


def retrieve_test_file(*, source: Path, target: Path) -> None:
    target.parent.mkdir(exist_ok=True, parents=True)
    shutil.copy(
        test_data_path / source,
        target,
    )


@pytest.fixture(scope="module")
def review_manager(session_mocker, tmp_path_factory: Path, request) -> colrev.review_manager.ReviewManager:  # type: ignore
    global test_data_path
    test_data_path = Path(request.fspath).parents[1] / Path("data")

    env_dir = tmp_path_factory.mktemp("test_repo")  # type: ignore

    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.register_repo",
        return_value=(),
    )

    def load_test_records(test_data_path) -> dict:  # type: ignore
        test_records_dict: typing.Dict[Path, dict] = {}
        bib_files_to_index = test_data_path / Path("local_index")
        for file_path in bib_files_to_index.glob("**/*"):
            test_records_dict[Path(file_path.name)] = {}

        for path in test_records_dict.keys():
            with open(bib_files_to_index.joinpath(path), encoding="utf-8") as file:
                parser = bibtex.Parser()
                bib_data = parser.parse_string(file.read())
                test_records_dict[path] = colrev.dataset.Dataset.parse_records_dict(
                    records_dict=bib_data.entries
                )
        return test_records_dict

    temp_sqlite = env_dir / Path("sqlite_index_test.db")
    with session_mocker.patch.object(
        colrev.env.local_index.LocalIndex, "SQLITE_PATH", temp_sqlite
    ):
        test_records_dict = load_test_records(test_data_path)
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

    test_repo_dir = tmp_path_factory.mktemp("test_review_example")  # type: ignore
    os.chdir(test_repo_dir)

    colrev.review_manager.ReviewManager.REPORT_RELATIVE.write_text(
        "test", encoding="utf-8"
    )

    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    review_manager.settings = colrev.settings.load_settings(
        settings_path=test_data_path.parents[1]
        / Path("colrev/template/init/settings.json")
    )
    with pytest.raises(colrev_exceptions.RepoInitError):
        review_manager.get_init_operation(
            review_type="literature_review",
            example=True,
            local_pdf_collection=True,
            target_path=test_repo_dir,
        )
    with pytest.raises(colrev_exceptions.ParameterError):
        review_manager.get_init_operation(
            review_type="misspelled_review", target_path=test_repo_dir
        )

    review_manager.settings.project.title = "topic a - a review"
    review_manager.get_init_operation(
        review_type="literature_review",
        example=True,
        target_path=test_repo_dir,
        light=True,
    )

    test_repo_dir = tmp_path_factory.mktemp("test_repo_local_pdf_collection")  # type: ignore
    os.chdir(test_repo_dir)
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    review_manager.settings = colrev.settings.load_settings(
        settings_path=test_data_path.parents[1]
        / Path("colrev/template/init/settings.json")
    )

    review_manager.get_init_operation(
        review_type="curated_masterdata",
        example=False,
        local_pdf_collection=True,
    )

    test_repo_dir = tmp_path_factory.mktemp("test_repo")  # type: ignore
    os.chdir(test_repo_dir)
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    review_manager.settings = colrev.settings.load_settings(
        settings_path=test_data_path.parents[1]
        / Path("colrev/template/init/settings.json")
    )

    # A .report.log file that should be removed
    (test_repo_dir / colrev.review_manager.ReviewManager.REPORT_RELATIVE).write_text(
        "test", encoding="utf-8"
    )
    Path("test.txt").write_text("test", encoding="utf-8")
    with pytest.raises(colrev_exceptions.NonEmptyDirectoryError):
        review_manager.get_init_operation(
            review_type="literature_review", example=False, target_path=test_repo_dir
        )
    Path("test.txt").unlink()

    review_manager.get_init_operation(
        review_type="literature_review", example=False, target_path=test_repo_dir
    )

    # Note: the strategy is to test the workflow and the endpoints separately
    # We therefore deactivate the (most time consuming endpoints) in the following
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(review_manager.path)
    )

    # def test_check_operation_precondition(review_manager: colrev.review_manager.ReviewManager) -> None:
    dedupe_operation = review_manager.get_dedupe_operation()
    dedupe_operation.review_manager.settings.project.delay_automated_processing = True
    with pytest.raises(colrev_exceptions.NoRecordsError):
        colrev.record.RecordStateModel.check_operation_precondition(
            operation=dedupe_operation
        )
    dedupe_operation.review_manager.settings.project.delay_automated_processing = False

    retrieve_test_file(
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
    return review_manager


def test_load(review_manager: colrev.review_manager.ReviewManager) -> None:
    load_operation = review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources, keep_ids=False, combine_commits=False)


def test_check_operation_precondition(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    dedupe_operation = review_manager.get_dedupe_operation()
    dedupe_operation.review_manager.settings.project.delay_automated_processing = True
    with pytest.raises(colrev_exceptions.ProcessOrderViolation):
        colrev.record.RecordStateModel.check_operation_precondition(
            operation=dedupe_operation
        )
    dedupe_operation.review_manager.settings.project.delay_automated_processing = False


def test_load_pubmed(review_manager: colrev.review_manager.ReviewManager) -> None:
    current_commit = review_manager.dataset.get_last_commit_sha()

    pubmed_file = test_data_path / Path("search_files/pubmed-chatbot.csv")
    shutil.copy(
        pubmed_file, review_manager.path / Path("data/search/pubmed-chatbot.csv")
    )
    load_operation = review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    new_sources[0].endpoint = "colrev.pubmed"
    load_operation.main(new_sources=new_sources, keep_ids=False, combine_commits=False)

    expected = (
        test_data_path / Path("search_files/pubmed-chatbot-expected.bib")
    ).read_text()
    actual = (review_manager.path / Path("data/search/pubmed-chatbot.bib")).read_text()
    assert expected == actual

    repo = git.Repo(review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)

    review_manager.load_settings()


def test_prep(review_manager: colrev.review_manager.ReviewManager) -> None:
    prep_operation = review_manager.get_prep_operation()
    current_commit = review_manager.dataset.get_last_commit_sha()
    prep_operation.skip_prep()
    repo = git.Repo(review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)

    prep_operation.main(keep_ids=False)

    current_commit = review_manager.dataset.get_last_commit_sha()

    prep_operation.set_ids()
    # TODO : difference set_ids - reset_ids?
    prep_operation.setup_custom_script()
    prep_operation.reset_ids()

    repo = git.Repo(review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)


def test_prep_manp(review_manager: colrev.review_manager.ReviewManager) -> None:
    prep_man_operation = review_manager.get_prep_man_operation()
    prep_man_operation.prep_man_stats()
    prep_man_operation.main()


def test_search(review_manager: colrev.review_manager.ReviewManager) -> None:
    search_operation = review_manager.get_search_operation()
    search_operation.main(rerun=True)

    search_operation.view_sources()


def test_search_get_unique_filename(
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    search_operation = review_manager.get_search_operation()
    expected = Path("data/search/test_records_1.bib")
    actual = search_operation.get_unique_filename(file_path_string="test_records.bib")
    print(actual)
    assert expected == actual


def test_dedupe(review_manager: colrev.review_manager.ReviewManager) -> None:
    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.main()


def test_prescreen(review_manager: colrev.review_manager.ReviewManager) -> None:
    prescreen_operation = review_manager.get_prescreen_operation()
    prescreen_operation.create_prescreen_split(create_split=2)
    review_manager.settings.prescreen.prescreen_package_endpoints = [
        {"endpoint": "colrev.conditional_prescreen"}
    ]
    prescreen_operation.main(split_str="NA")
    prescreen_operation.include_all_in_prescreen(persist=False)

    current_commit = review_manager.dataset.get_last_commit_sha()
    prescreen_operation.setup_custom_script()
    repo = git.Repo(review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)


def test_pdf_get(review_manager: colrev.review_manager.ReviewManager) -> None:
    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.main()


def test_pdf_prep(review_manager: colrev.review_manager.ReviewManager) -> None:
    pdf_prep_operation = review_manager.get_pdf_prep_operation(reprocess=False)
    pdf_prep_operation.main(batch_size=0)


def test_pdf_discard(review_manager: colrev.review_manager.ReviewManager) -> None:
    pdf_get_man_operation = review_manager.get_pdf_get_man_operation()
    pdf_get_man_operation.discard()


def test_pdf_prep_man(review_manager: colrev.review_manager.ReviewManager) -> None:
    pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation()
    pdf_prep_man_operation.main()
    pdf_prep_man_operation.pdf_prep_man_stats()
    pdf_prep_man_operation.extract_needs_pdf_prep_man()
    pdf_prep_man_operation.discard()


def test_screen(review_manager: colrev.review_manager.ReviewManager) -> None:
    screen_operation = review_manager.get_screen_operation()
    review_manager.settings.screen.screen_package_endpoints = []
    screen_operation.main(split_str="NA")
    screen_operation.include_all_in_screen(persist=False)
    screen_operation.create_screen_split(create_split=2)

    current_commit = review_manager.dataset.get_last_commit_sha()
    screen_operation.setup_custom_script()
    repo = git.Repo(review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)


def test_data(review_manager: colrev.review_manager.ReviewManager) -> None:
    data_operation = review_manager.get_data_operation()
    data_operation.main()
    review_manager.create_commit(msg="Data and synthesis", manual_author=True)
    data_operation.profile()

    current_commit = review_manager.dataset.get_last_commit_sha()
    data_operation.setup_custom_script()
    repo = git.Repo(review_manager.path)
    repo.head.reset(current_commit, index=True, working_tree=True)

    review_manager.load_settings()


def test_checks(review_manager: colrev.review_manager.ReviewManager) -> None:
    checker = colrev.checker.Checker(review_manager=review_manager)

    expected = ["0.7.1", "0.7.1"]
    actual = checker.get_colrev_versions()
    assert expected == actual

    checker.check_repository_setup()

    assert True == checker.in_virtualenv()

    expected = []
    actual = checker.check_repo_extended()
    assert expected == actual

    expected = {"status": 0, "msg": "Everything ok."}  # type: ignore
    actual = checker.check_repo()  # type: ignore
    assert expected == actual

    expected = []
    actual = checker.check_repo_basics()
    assert expected == actual

    expected = []
    actual = checker.check_change_in_propagated_id(
        prior_id="Srivastava2015",
        new_id="Srivastava2015a",
        project_context=review_manager.path,
    )
    assert expected == actual

    review_manager.get_search_sources()
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
    search_sources = review_manager.settings.sources
    actual = [asdict(s) for s in search_sources]  # type: ignore
    assert expected == actual
