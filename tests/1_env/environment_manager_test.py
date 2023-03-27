#!/usr/bin/env python
import os
import typing
from pathlib import Path

import pytest
from pybtex.database.input import bibtex

import colrev.env.environment_manager
import colrev.env.tei_parser
import colrev.review_manager


@pytest.fixture(scope="module")
def script_loc(request) -> Path:  # type: ignore
    """Return the directory of the currently running test script"""

    return Path(request.fspath).parent


def test_environment_manager(mocker, tmp_path, script_loc) -> None:  # type: ignore
    identifier_list = ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    if any("true" == os.getenv(x) for x in identifier_list):
        return

    temp_env = tmp_path
    with mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "registry",
        temp_env / Path("reg.yml"),
    ):
        env_man = colrev.env.environment_manager.EnvironmentManager()

        expected = [  # type: ignore
            {
                "repo_name": "colrev",
                "repo_source_path": Path(colrev.__file__).parents[1],
                "repo_source_url": "https://github.com/CoLRev-Environment/colrev.git",
            }
        ]
        print(script_loc)
        env_man.register_repo(path_to_register=Path(script_loc.parents[1]))
        actual = env_man.environment_registry  # type: ignore
        print(actual)
        assert expected == actual

        expected = {  # type: ignore
            "index": {
                "size": 0,
                "last_modified": "NOT_INITIATED",
                "path": "/home/gerit/colrev",
                "status": "TODO",
            },
            "local_repos": {
                "repos": [],
                "broken_links": [
                    {
                        "repo_name": "colrev",
                        "repo_source_path": str(Path(colrev.__file__).parents[1]),
                        "repo_source_url": "https://github.com/CoLRev-Environment/colrev.git",
                    }
                ],
            },
        }
        actual = env_man.get_environment_details()  # type: ignore
        print(actual)
        assert expected == actual

        env_man.stop_docker_services()

        # env_man.build_docker_image()

        # env_man.save_environment_registry(updated_registry=env_man.environment_registry)
