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
import colrev.review_manager
import colrev.settings


@pytest.fixture(scope="module")
def script_loc(request) -> Path:  # type: ignore
    """Return the directory of the currently running test script"""

    return Path(request.fspath).parent


def test_full_run(tmp_path: Path, mocker, script_loc: Path) -> None:  # type: ignore
    os.chdir(tmp_path)

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    def load_test_records(script_loc) -> dict:  # type: ignore
        # local_index_bib_path = script_loc.joinpath("local_index.bib")

        test_records_dict: typing.Dict[Path, dict] = {}
        bib_files_to_index = Path(script_loc.parent / Path("minimal")) / Path(
            "local_index"
        )
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

    temp_sqlite = tmp_path / Path("sqlite_index_test.db")
    print(temp_sqlite)
    with mocker.patch.object(
        colrev.env.local_index.LocalIndex, "SQLITE_PATH", temp_sqlite
    ):
        test_records_dict = load_test_records(script_loc)
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

    for filename in os.listdir(tmp_path):
        file_path = os.path.join(tmp_path, filename)
        # try:
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.unlink(file_path)
        #     elif os.path.isdir(file_path):
        #         shutil.rmtree(file_path)
        # except Exception as e:
        #     print(f"Failed to delete {file_path}. Reason: {e}")

    colrev.review_manager.ReviewManager.get_init_operation(
        review_type="literature_review",
        example=False,
    )

    # Note: the strategy is to test the workflow and the endpoints separately
    # We therefore deactivate the (most time consuming endpoints) in the following
    review_manager = colrev.review_manager.ReviewManager()
    colrev.env.utils.retrieve_package_file(
        template_file=Path("template/example/test_records.bib"),
        target=Path("data/search/test_records.bib"),
    )
    review_manager.dataset.add_changes(path=Path("data/search/test_records.bib"))
    review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev_built_in.resolve_crossrefs"},
        {"endpoint": "colrev_built_in.source_specific_prep"},
        {"endpoint": "colrev_built_in.exclude_non_latin_alphabets"},
        {"endpoint": "colrev_built_in.exclude_collections"},
    ]
    review_manager.settings.dedupe.dedupe_package_endpoints = [
        {"endpoint": "colrev_built_in.simple_dedupe"}
    ]

    review_manager.settings.pdf_get.pdf_get_package_endpoints = [
        {"endpoint": "colrev_built_in.local_index"}
    ]
    review_manager.settings.pdf_prep.pdf_prep_package_endpoints = []
    review_manager.settings.data.data_package_endpoints = []
    review_manager.save_settings()

    review_manager.logger.info("Start load")
    load_operation = review_manager.get_load_operation()

    load_operation = review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources, keep_ids=False, combine_commits=False)

    review_manager.logger.info("Start prep")
    review_manager = colrev.review_manager.ReviewManager()
    prep_operation = review_manager.get_prep_operation()
    prep_operation.main(keep_ids=False)

    search_operation = review_manager.get_search_operation()
    search_operation.main(rerun=True)

    review_manager.logger.info("Start dedupe")
    review_manager = colrev.review_manager.ReviewManager()
    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.main()

    review_manager.logger.info("Start prescreen")
    review_manager = colrev.review_manager.ReviewManager()
    prescreen_operation = review_manager.get_prescreen_operation()
    prescreen_operation.include_all_in_prescreen(persist=False)

    review_manager.logger.info("Start pdf-get")
    review_manager = colrev.review_manager.ReviewManager()
    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.main()

    review_manager.logger.info("Start pdf-prep")
    review_manager = colrev.review_manager.ReviewManager()
    pdf_prep_operation = review_manager.get_pdf_prep_operation(reprocess=False)
    pdf_prep_operation.main(batch_size=0)

    review_manager.logger.info("Start pdfs discard")
    review_manager = colrev.review_manager.ReviewManager()
    pdf_get_man_operation = review_manager.get_pdf_get_man_operation()
    pdf_get_man_operation.discard()

    review_manager = colrev.review_manager.ReviewManager()
    pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation()
    pdf_prep_man_operation.discard()

    review_manager.logger.info("Start screen")
    review_manager = colrev.review_manager.ReviewManager()
    screen_operation = review_manager.get_screen_operation()
    screen_operation.include_all_in_screen(persist=False)

    review_manager.logger.info("Start pdfs data")
    review_manager = colrev.review_manager.ReviewManager()
    data_operation = review_manager.get_data_operation()
    data_operation.main()
    review_manager.create_commit(msg="Data and synthesis", manual_author=True)

    print(tmp_path)

    checker = colrev.checker.Checker(review_manager=review_manager)

    expected = ["0.7.1", "0.7.1"]
    actual = checker.get_colrev_versions()
    assert expected == actual

    checker.check_repository_setup()

    assert False == checker.in_virtualenv()
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
        prior_id="Srivastava2015", new_id="Srivastava2015a", project_context=tmp_path
    )
    assert expected == actual

    review_manager.get_search_sources()
    expected = [  # type: ignore
        {  # type: ignore
            "endpoint": "colrev_built_in.pdfs_dir",
            "filename": Path("data/search/pdfs.bib"),
            "search_type": colrev.settings.SearchType.PDFS,
            "search_parameters": {"scope": {"path": "data/pdfs"}},
            "load_conversion_package_endpoint": {"endpoint": "colrev_built_in.bibtex"},
            "comment": "",
        },
        {  # type: ignore
            "endpoint": "colrev_built_in.unknown_source",
            "filename": Path("data/search/test_records.bib"),
            "search_type": colrev.settings.SearchType.DB,
            "search_parameters": {},
            "load_conversion_package_endpoint": {"endpoint": "colrev_built_in.bibtex"},
            "comment": None,
        },
    ]
    search_sources = review_manager.settings.sources
    actual = [asdict(s) for s in search_sources]  # type: ignore
    assert expected == actual


# Note : must run after full_run_test
# because the review_manager requires a valid CoLRev repository


def test_review_type_interfaces(mocker) -> None:  # type: ignore
    # Test whether the review_type definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()

    g = git.Git()
    g.execute(["git", "reset", "--hard", "HEAD"])
    package_manager = review_manager.get_package_manager()
    load_operation = review_manager.get_load_operation()

    review_type_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.review_type,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.review_type,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in review_type_identifiers
        ],
        operation=load_operation,
        instantiate_objects=True,
    )


def test_search_source_interfaces(mocker) -> None:  # type: ignore
    # Test whether the interface definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    load_operation = review_manager.get_load_operation(
        notify_state_transition_operation=False
    )

    search_source_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.search_source,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.search_source,
        selected_packages=[
            {
                "endpoint": p,
                "filename": Path("test.bib"),
                "search_type": colrev.settings.SearchType.DB,
                "search_parameters": {"scope": {"path": "test"}},
                "load_conversion_package_endpoint": {
                    "endpoint": "colrev_built_in.bibtex"
                },
                "comment": "",
                "interface_test": True,
            }
            for p in search_source_identifiers
        ],
        operation=load_operation,
        instantiate_objects=True,
    )


def test_load_conversion_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the load_conversion definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    load_operation = review_manager.get_load_operation(
        notify_state_transition_operation=False
    )

    load_conversion_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.load_conversion,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.load_conversion,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in load_conversion_identifiers
        ],
        operation=load_operation,
        instantiate_objects=True,
    )


def test_prep_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the prep definitions are correct
    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    prep_operation = review_manager.get_prep_operation(
        notify_state_transition_operation=False
    )

    prep_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prep,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prep,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in prep_identifiers
        ],
        operation=prep_operation,
        instantiate_objects=True,
    )


def test_prep_man_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the prep_man definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    prep_man_operation = review_manager.get_prep_man_operation(
        notify_state_transition_operation=False
    )

    prep_man_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prep_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prep_man,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in prep_man_identifiers
        ],
        operation=prep_man_operation,
        instantiate_objects=True,
    )


def test_dedupe_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the dedupe definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=False
    )

    dedupe_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.dedupe,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.dedupe,
        selected_packages=[
            {"endpoint": p}
            for p in dedupe_identifiers
            if p not in ["colrev_built_in.curation_full_outlet_dedupe"]
        ]
        + [
            {
                "endpoint": "colrev_built_in.curation_full_outlet_dedupe",
                "selected_source": "test",
            },
        ],
        operation=dedupe_operation,
        instantiate_objects=True,
    )


def test_prescreen_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the prescreen definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    prescreen_operation = review_manager.get_prescreen_operation(
        notify_state_transition_operation=False
    )

    prescreen_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prescreen,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.prescreen,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in prescreen_identifiers
            # Note : asreview dependency fails on gh actions
            if p not in ["colrev_built_in.asreview_prescreen"]
        ],
        operation=prescreen_operation,
        instantiate_objects=True,
    )


def test_pdf_get_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the pdf_get definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=False
    )

    pdf_get_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_get,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_get,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in pdf_get_identifiers
        ],
        operation=pdf_get_operation,
        instantiate_objects=True,
    )


def test_pdf_get_man_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the pdf_get_man definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    pdf_get_man_operation = review_manager.get_pdf_get_man_operation(
        notify_state_transition_operation=False
    )

    pdf_get_man_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_get_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_get_man,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in pdf_get_man_identifiers
        ],
        operation=pdf_get_man_operation,
        instantiate_objects=True,
    )


def test_pdf_prep_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the pdf_prep definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    pdf_prep_operation = review_manager.get_pdf_prep_operation(
        notify_state_transition_operation=False
    )

    pdf_prep_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in pdf_prep_identifiers
        ],
        operation=pdf_prep_operation,
        instantiate_objects=True,
    )


def test_pdf_prep_man_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the pdf_prep_man definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation(
        notify_state_transition_operation=False
    )

    pdf_prep_man_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep_man,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep_man,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in pdf_prep_man_identifiers
        ],
        operation=pdf_prep_man_operation,
        instantiate_objects=True,
    )


def test_screen_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the screen definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    screen_operation = review_manager.get_screen_operation(
        notify_state_transition_operation=False
    )

    screen_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.screen,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.screen,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in screen_identifiers
        ],
        operation=screen_operation,
        instantiate_objects=True,
    )


def test_data_package_interfaces(mocker) -> None:  # type: ignore
    # Test whether the data definitions are correct

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    review_manager = colrev.review_manager.ReviewManager()
    package_manager = review_manager.get_package_manager()
    data_operation = review_manager.get_data_operation(
        notify_state_transition_operation=False
    )

    data_identifiers = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.data,
        installed_only=True,
    )
    package_manager.load_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.data,
        selected_packages=[
            {
                "endpoint": p,
            }
            for p in data_identifiers
            if p
            not in [
                "colrev_built_in.obsidian",
                "colrev_built_in.colrev_curation",
            ]
        ]
        + [
            {"endpoint": "colrev_built_in.obsidian", "version": "0.1.0", "config": {}},
            {
                "endpoint": "colrev_built_in.colrev_curation",
                "curation_url": "",
                "curated_masterdata": True,
                "masterdata_restrictions": {},
                "curated_fields": [],
            },
        ],
        operation=data_operation,
        instantiate_objects=True,
    )
