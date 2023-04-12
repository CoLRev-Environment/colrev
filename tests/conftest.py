#!/usr/bin/env python
import os
import shutil
import typing
from pathlib import Path

import git
import pytest
from pybtex.database.input import bibtex

import colrev.review_manager


class Helpers:
    test_data_path = Path(__file__).parent / Path("data")

    @staticmethod
    def retrieve_test_file(*, source: Path, target: Path) -> None:
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy(
            Helpers.test_data_path / source,
            target,
        )


@pytest.fixture(scope="session")
def helpers():  # type: ignore
    return Helpers


@pytest.fixture(scope="session")
def base_repo_review_manager_setup(session_mocker, tmp_path_factory, helpers):  # type: ignore
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
    repo = git.Repo()
    commit = repo.head.object.hexsha
    review_manager.commit = commit

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

    return review_manager


@pytest.fixture
def base_repo_review_manager(base_repo_review_manager_setup):  # type: ignore
    """Resets the repo state for base_repo_review_manager_setup"""
    os.chdir(str(base_repo_review_manager_setup.path))
    repo = git.Repo(base_repo_review_manager_setup.path)
    repo.git.reset("--hard", base_repo_review_manager_setup.commit)
    return base_repo_review_manager_setup
