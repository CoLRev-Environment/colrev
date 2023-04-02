#!/usr/bin/env python
import os
import shutil
from pathlib import Path

import git
import pytest

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
def base_repo_review_manager_setup(session_mocker, tmp_path_factory):  # type: ignore
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
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    review_manager.get_init_operation(
        review_type="literature_review",
        target_path=test_repo_dir,
    )
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    repo = git.Repo()
    commit = repo.head.object.hexsha
    review_manager.commit = commit
    return review_manager


@pytest.fixture
def base_repo_review_manager(base_repo_review_manager_setup):  # type: ignore
    """Resets the repo state for base_repo_review_manager_setup"""
    os.chdir(str(base_repo_review_manager_setup.path))
    repo = git.Repo(base_repo_review_manager_setup.path)
    repo.git.reset("--hard", base_repo_review_manager_setup.commit)
    return base_repo_review_manager_setup
