import shutil
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from colrev.constants import Filepaths
from colrev.env import resources


def test_install_curated_resource_empty(tmp_path):  # type: ignore

    curated_resource = "example/repo"
    mock_git = MagicMock()

    with patch("git.Repo.clone_from", return_value=mock_git) as mock_method:
        resource_manager = resources.Resources()
        original_curations_path = Filepaths.CURATIONS_PATH
        Filepaths.CURATIONS_PATH = tmp_path
        repo_dir = Filepaths.CURATIONS_PATH / Path(curated_resource.split("/")[-1])

        resource_manager.install_curated_resource(curated_resource=curated_resource)
        mock_method.assert_called_once()
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        Filepaths.CURATIONS_PATH = original_curations_path


def test_install_curated_resource_with_records(tmp_path, mocker):  # type: ignore

    curated_resource = "example/repo"

    def patched_clone_from(curated_repo, repo_dir, depth):  # type: ignore
        (repo_dir / Path("README.md")).parent.mkdir(parents=True, exist_ok=True)
        (repo_dir / Path("README.md")).write_text(
            """# Readme

To install this curation, run
colrev env --install example/repo

The following repositories are part of the curation:

colrev env --install example/repo2
"""
        )
        return True

    mocker.patch(
        "git.Repo.clone_from",
        side_effect=patched_clone_from,
    )
    resource_manager = resources.Resources()
    resource_manager.curations_path = tmp_path
    repo_dir = resource_manager.curations_path / Path(curated_resource.split("/")[-1])

    resource_manager.install_curated_resource(curated_resource=curated_resource)
    if repo_dir.exists():
        shutil.rmtree(repo_dir)


def test_install_curated_resource_with_readme(tmp_path, mocker):  # type: ignore

    curated_resource = "example/repo"

    def patched_clone_from(curated_repo, repo_dir, depth):  # type: ignore
        (repo_dir / Path("data/records.bib")).parent.mkdir(parents=True, exist_ok=True)
        (repo_dir / Path("data/records.bib")).write_text("test")
        return True

    mocker.patch(
        "git.Repo.clone_from",
        side_effect=patched_clone_from,
    )
    resource_manager = resources.Resources()
    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.register_repo",
        return_value=True,
    )
    resource_manager.curations_path = tmp_path
    repo_dir = resource_manager.curations_path / Path(curated_resource.split("/")[-1])

    resource_manager.install_curated_resource(curated_resource=curated_resource)
    if repo_dir.exists():
        shutil.rmtree(repo_dir)


def test_install_curated_resource_already_exists(tmp_path, mocker):  # type: ignore

    curated_resource = "example/repo"

    def patched_clone_from(curated_repo, repo_dir, depth):  # type: ignore
        (repo_dir / Path("data/records.bib")).parent.mkdir(parents=True, exist_ok=True)
        (repo_dir / Path("data/records.bib")).write_text("test")
        return True

    mocker.patch(
        "git.Repo.clone_from",
        side_effect=patched_clone_from,
    )
    resource_manager = resources.Resources()
    resource_manager.curations_path = tmp_path
    repo_dir = resource_manager.curations_path / Path(curated_resource.split("/")[-1])
    Path(repo_dir).mkdir()
    resource_manager.install_curated_resource(curated_resource=curated_resource)
