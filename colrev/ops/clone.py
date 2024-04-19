#! /usr/bin/env python
"""Clone CoLRev repositories."""
import os
from pathlib import Path

from git import Repo

import colrev.env.local_index_builder
import colrev.exceptions as colrev_exceptions
import colrev.review_manager


class Clone:
    """Clone CoLRev project from git remote repository"""

    # pylint: disable=too-few-public-methods

    def __init__(self, *, git_url: str) -> None:
        self.git_url = git_url
        """The git remote URL"""

        git_repo_name = git_url[git_url.rfind("/") + 1 :]
        self.local_path = Path.cwd() / Path(git_repo_name)

    def clone_git_repo(self) -> None:
        """Method to clone a CoLRev project from git remote repository"""

        Repo.clone_from(self.git_url, str(self.local_path))
        os.chdir(str(self.local_path))
        try:
            review_manager = colrev.review_manager.ReviewManager(
                path_str=str(self.local_path)
            )
            review_manager.check_repository_setup()
        except colrev_exceptions.RepoSetupError:
            print("Not a CoLRev repository.")
            return
        environment_manager = review_manager.get_environment_manager()
        environment_manager.register_repo(self.local_path)
        local_index_builder = colrev.env.local_index_builder.LocalIndexBuilder()

        local_index_builder.index_colrev_project(self.local_path)
