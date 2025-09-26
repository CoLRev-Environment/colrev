#!/usr/bin/env python
"""Testing environment manager settings"""
import json
import os
from collections import namedtuple
from pathlib import Path

import git
import pytest

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.review_manager
from colrev.constants import Filepaths
from colrev.packages.unpaywall.src.unpaywall import Unpaywall

# flake8: noqa: E501

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

    base_path = script_loc.parents[2]
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


def test_dict_keys_exists_with_one_argument() -> None:
    env_man = colrev.env.environment_manager.EnvironmentManager()
    with pytest.raises(AttributeError):
        env_man._dict_keys_exists({}, "test")


def test_register_ports() -> None:

    env_man = colrev.env.environment_manager.EnvironmentManager()
    env_man.register_ports(["3000", "3001", "3002"])
    with pytest.raises(colrev_exceptions.PortAlreadyRegisteredException):
        env_man.register_ports(["3000", "3001", "3002"])


def test_repo_registry(tmp_path) -> None:  # type: ignore
    env_man = colrev.env.environment_manager.EnvironmentManager()
    env_man.environment_registry = {"local_index": {"repos": []}}
    actual = env_man.local_repos()
    assert actual == []

    os.chdir(tmp_path)
    git_repo = git.Repo.init()

    remote_url = "https://github.com/your-username/your-repo.git"
    git_repo.create_remote("origin", remote_url)

    env_man.register_repo(path_to_register=tmp_path)
    assert (
        env_man.environment_registry["local_index"]["repos"][0]["repo_source_url"]
        == remote_url
    )

    # Test if the repo is already registered
    env_man.register_repo(path_to_register=tmp_path)
    assert len(env_man.environment_registry["local_index"]["repos"]) == 1


def test_get_environment_details(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    # Note: test only runs locally on my machine
    if "gerit" not in str(base_repo_review_manager.path):
        return

    env_man = colrev.env.environment_manager.EnvironmentManager()
    env_man.environment_registry = {"local_index": {"repos": []}}
    env_man.environment_registry["local_index"]["repos"] = [
        {
            "repo_name": "international-conference-on-information-systems",
            "repo_source_path": str(
                Filepaths.CURATIONS_PATH.joinpath(
                    "international-conference-on-information-systems"
                )
            ),
            "repo_source_url": str(
                Filepaths.CURATIONS_PATH.joinpath(
                    "international-conference-on-information-systems"
                )
            ),
        },
        {
            "repo_name": "european-journal-of-information-systems",
            "repo_source_path": str(
                Filepaths.CURATIONS_PATH.joinpath(
                    "european-journal-of-information-systems"
                )
            ),
            "repo_source_url": str(
                Filepaths.CURATIONS_PATH.joinpath(
                    "european-journal-of-information-systems"
                )
            ),
        },
        {
            "repo_name": "information-systems-journal",
            "repo_source_path": str(
                Filepaths.CURATIONS_PATH.joinpath("information-systems-journal")
            ),
            "repo_source_url": str(
                Filepaths.CURATIONS_PATH.joinpath("information-systems-journal")
            ),
        },
    ]
    env_man.save_environment_registry(updated_registry=env_man.environment_registry)

    ret = env_man.get_environment_details()

    assert "index" in ret
    assert "local_repos" in ret
    assert "repos" in ret["local_repos"]
    assert "broken_links" in ret["local_repos"]


def test_get_curated_outlets(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    # Note: test only runs locally on my machine
    if "gerit" not in str(base_repo_review_manager.path):
        return

    env_man = colrev.env.environment_manager.EnvironmentManager()
    env_man.environment_registry = {"local_index": {"repos": []}}
    env_man.environment_registry["local_index"]["repos"] = [
        {
            "repo_name": "international-conference-on-information-systems",
            "repo_source_path": str(
                Filepaths.CURATIONS_PATH.joinpath(
                    "international-conference-on-information-systems"
                )
            ),
            "repo_source_url": "https://github.com/CoLRev-curations/international-conference-on-information-systems",
        },
        {
            "repo_name": "european-journal-of-information-systems",
            "repo_source_path": str(
                Filepaths.CURATIONS_PATH.joinpath(
                    "european-journal-of-information-systems"
                )
            ),
            "repo_source_url": "https://github.com/CoLRev-curations/european-journal-of-information-systems",
        },
        {
            "repo_name": "information-systems-journal",
            "repo_source_path": str(
                Filepaths.CURATIONS_PATH.joinpath("information-systems-journal")
            ),
            "repo_source_url": "https://github.com/CoLRev-curations/information-systems-journal",
        },
    ]
    env_man.save_environment_registry(updated_registry=env_man.environment_registry)

    ret = env_man.get_curated_outlets()
    print(ret)
    assert ret == [
        "International Conference on Information Systems",
        "European Journal of Information Systems",
        "Information Systems Journal",
    ]
