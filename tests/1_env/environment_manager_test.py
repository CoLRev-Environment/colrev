#!/usr/bin/env python
"""Testing environment manager settings"""
import json
import os
from collections import namedtuple
from pathlib import Path

import docker
import git
import pytest

import colrev.env.environment_manager
import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
import colrev.review_manager
from colrev.ops.built_in.pdf_get.unpaywall import Unpaywall


EnvTestConf = namedtuple(
    "EnvTestConf",
    "json_path expected_json yaml_path expected_yaml base_path test_repo backup",
)


def continue_test() -> bool:
    """Skip test if running inside CI"""
    return not any(
        "true" == os.getenv(x)
        for x in ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    )


def prep_test(tmp_path, script_loc) -> EnvTestConf:  # type: ignore
    """
    Previous version stores files in yml, upgraded to JSON format,
    and keep the previous version available, will check for yaml file, if found,
    load it and save it as a json file. After saved, will rename the old yaml file
    to a file with bk extension

    """
    long_path = tmp_path / Path(
        "a/really long/path/with some/spaces/should/not/cause/any issues/when writing/"
    )
    long_path.mkdir(parents=True)
    print(long_path)
    test_repo = long_path / Path("a_test_repo")
    dummy_origin = "https://example.com/repo"

    base_path = script_loc.parents[1]
    repo = git.Repo(base_path)
    origin = list(repo.remote("origin").urls)

    expected_yaml = f"""- repo_name: colrev
  repo_source_path: {base_path}
  repo_source_url: {origin[0]}
- repo_name: a_test_repo
  repo_source_path: {test_repo}
  repo_source_url: {dummy_origin}
"""
    expected_json = json.dumps(
        {
            "local_index": {
                "repos": [
                    {
                        "repo_name": "colrev",
                        "repo_source_path": str(base_path),
                        "repo_source_url": str(origin[0]),
                    },
                    {
                        "repo_name": "a_test_repo",
                        "repo_source_path": str(test_repo),
                        "repo_source_url": dummy_origin,
                    },
                ],
            },
            "packages": {},
        }
    )

    # create a repo and make a commit
    repo = git.Repo.init(test_repo)
    repo.create_remote(name="origin", url=dummy_origin)
    with open(test_repo / "test.yaml", "w", encoding="utf-8") as file:
        file.write(expected_yaml)
    repo.index.add(["test.yaml"])
    repo.index.commit("initial commit")
    #
    # return base_path, test_json_path, expected_json, test_repo
    return EnvTestConf(
        base_path=base_path,
        json_path=tmp_path / Path("reg.json"),
        expected_json=expected_json,
        yaml_path=tmp_path / Path("reg.yaml"),
        expected_yaml=expected_yaml,
        test_repo=test_repo,
        backup=tmp_path / Path("reg.yaml.bk"),
    )


def test_loading_config_properly(  # type: ignore
    _patch_registry, tmp_path, script_loc
) -> None:
    """
    Testing if we are loading existing json registry file correctly
    """
    if not continue_test():
        return
    data = prep_test(tmp_path, script_loc)
    with open(data.json_path, "w", encoding="utf-8") as file:
        file.write(data.expected_json)
    env_man = colrev.env.environment_manager.EnvironmentManager()
    assert json.dumps(env_man.environment_registry) == data.expected_json
    assert not env_man.load_yaml


def test_saving_config_file_as_json_from_yaml_correctly(  # type: ignore
    _patch_registry,
    tmp_path,
    script_loc,
) -> None:
    """
    Testing if we are converting a yaml file to json correctly
    """
    if not continue_test():
        return
    data = prep_test(tmp_path, script_loc)
    with open(data.yaml_path, "w", encoding="utf-8") as file:
        file.write(data.expected_yaml)
    env_man = colrev.env.environment_manager.EnvironmentManager()
    assert env_man.load_yaml
    assert Path(data.base_path).exists()
    env_man.register_repo(path_to_register=Path(data.base_path))
    env_man.register_repo(path_to_register=Path(data.test_repo))
    with open(data.json_path, encoding="utf-8") as file:
        actual_json = json.dumps(json.loads(file.read()))
        assert data.expected_json == actual_json


def test_setting_value(_patch_registry):  # type: ignore
    """
    Updating the registry
    """
    env_man = colrev.env.environment_manager.EnvironmentManager()
    test_user = {"email": "test@email.com"}

    env_man.update_registry(Unpaywall.SETTINGS["email"], test_user["email"])
    # Check with new env_man
    env_man = colrev.env.environment_manager.EnvironmentManager()

    cfg_email = env_man.get_settings_by_key("packages.pdf_get.colrev.unpaywall.email")

    assert test_user["email"] == cfg_email


def test_setting_value_with_missing_field(_patch_registry):  # type: ignore
    """
    Updating the registry
    """
    env_man = colrev.env.environment_manager.EnvironmentManager()
    test_user = {
        "username": "Tester Name",  # this value is set from mock
        "email": "test@email.com",
    }
    env_man.update_registry(
        "packages.pdf_get.colrev.unpaywall.username", test_user["username"]
    )
    env_man.update_registry(
        "packages.pdf_get.colrev.unpaywall.email", test_user["email"]
    )
    # Check with new env_man
    env_man = colrev.env.environment_manager.EnvironmentManager()
    cfg_username = env_man.get_settings_by_key(
        "packages.pdf_get.colrev.unpaywall.username"
    )
    cfg_email = env_man.get_settings_by_key("packages.pdf_get.colrev.unpaywall.email")
    assert (test_user["username"], test_user["email"]) == (cfg_username, cfg_email)


def test_update_registry_exception():  # type: ignore
    """
    Updating the registry
    """
    env_man = colrev.env.environment_manager.EnvironmentManager()
    test_user = {
        "username": "Tester Name",  # this value is set from mock
        "email": "test@email.com",
    }
    with pytest.raises(colrev_exceptions.PackageSettingMustStartWithPackagesException):
        env_man.update_registry(
            "xy.pdf_get.colrev.unpaywall.username", test_user["username"]
        )


def test_dict_keys_exists_with_one_argument():
    env_man = colrev.env.environment_manager.EnvironmentManager()
    with pytest.raises(AttributeError):
        env_man._dict_keys_exists("test")


def test_register_ports() -> None:

    env_man = colrev.env.environment_manager.EnvironmentManager()
    env_man.register_ports(["3000", "3001", "3002"])
    with pytest.raises(colrev_exceptions.PortAlreadyRegisteredException):
        env_man.register_ports(["3000", "3001", "3002"])


def test_get_environment_details() -> None:
    env_man = colrev.env.environment_manager.EnvironmentManager()
    ret = env_man.get_environment_details()
    print(ret)
    assert "index" in ret
    assert "local_repos" in ret
    assert "repos" in ret["local_repos"]
    assert "broken_links" in ret["local_repos"]


def test_get_curated_outlets() -> None:

    env_man = colrev.env.environment_manager.EnvironmentManager()
    ret = env_man.get_curated_outlets()
    print(ret)


def test_repo_registry(tmp_path) -> None:
    env_man = colrev.env.environment_manager.EnvironmentManager()
    actual = env_man.local_repos()
    assert actual == []

    os.chdir(tmp_path)
    git.Repo.init()
    env_man.register_repo(path_to_register=tmp_path)


def test_build_docker_image(tmp_path) -> None:  # type: ignore
    def remove_docker_image(image_name: str) -> None:
        client = docker.from_env()
        try:
            client.images.remove(image_name)
            print(f"Image '{image_name}' removed successfully.")
        except docker.errors.ImageNotFound:
            print(f"Image '{image_name}' not found.")

    env_man = colrev.env.environment_manager.EnvironmentManager()
    env_man.build_docker_image(imagename="hello-world")
    remove_docker_image("hello-world")

    # Docker not available on Windows (GH-Actions)
    if not continue_test():
        return

    # Create a simple Dockerfile
    dockerfile_content = """
    FROM python:3.9
    WORKDIR /app
    COPY . /app
    """

    # Save the Dockerfile
    dockerfile_path = tmp_path / Path("Dockerfile")
    with open(dockerfile_path, "w") as file:
        file.write(dockerfile_content)

    # Build the Docker image
    env_man.build_docker_image(imagename="test-image", dockerfile=dockerfile_path)
    remove_docker_image("test-image")
