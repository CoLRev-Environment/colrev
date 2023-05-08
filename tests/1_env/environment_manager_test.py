#!/usr/bin/env python
"""Testing environment manager settings"""
import json
import os
from collections import namedtuple
from pathlib import Path

import git

import colrev.env.environment_manager
import colrev.env.tei_parser
import colrev.review_manager

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


# def test_environment_manager(mocker, tmp_path, script_loc) -> None:  # type: ignore
#
#     if not continue_test():
#         return
#
#     with mocker.patch.object(
#             colrev.env.environment_manager.EnvironmentManager,
#             "registry",
#             tmp_path / Path("reg.yml"),
#     ):
#         env_man = colrev.env.environment_manager.EnvironmentManager()
#
#         env_man.register_repo(path_to_register=Path(script_loc.parents[1]))
#         actual = env_man.environment_registry  # type: ignore
#
#         expected = [  # type: ignore
#             {
#                 "repo_name": "colrev",
#                 "repo_source_path": Path(colrev.__file__).parents[1],
#                 "repo_source_url": actual[0]["repo_source_url"],
#             }
#         ]
#         assert expected == actual
#
#         expected = {  # type: ignore
#             "index": {
#                 "size": 0,
#                 "last_modified": "NOT_INITIATED",
#                 "path": "/home/gerit/colrev",
#                 "status": "TODO",
#             },
#             "local_repos": {
#                 "repos": [],
#                 "broken_links": [
#                     {
#                         "repo_name": "colrev",
#                         "repo_source_path": str(Path(colrev.__file__).parents[1]),
#                         "repo_source_url": str(actual[0]["repo_source_url"]),
#                     }
#                 ],
#             },
#         }
#         actual = env_man.get_environment_details()  # type: ignore
#         actual["index"]["path"] = "/home/gerit/colrev"  # type: ignore
#         assert expected == actual
