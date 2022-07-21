#! /usr/bin/env python
import os
from pathlib import Path

from colrev_core.environment import EnvironmentManager
from colrev_core.environment import LocalIndex
from colrev_core.review_manager import RepoSetupError
from colrev_core.review_manager import ReviewManager


class Clone:
    """Clone CoLRev project from git remote repository"""

    def __init__(self, git_url):
        self.git_url = git_url
        """The git remote URL"""

        git_repo_name = git_url[git_url.rfind("/") + 1 :]
        self.local_path = Path.cwd() / Path(git_repo_name)

    def clone_git_repo(self) -> None:
        """Method to clone a CoLRev project from git remote repository"""
        from git import Repo

        Repo.clone_from(self.git_url, str(self.local_path))
        os.chdir(str(self.local_path))
        try:
            REVIEW_MANAGER = ReviewManager(path_str=str(self.local_path))
            REVIEW_MANAGER.check_repository_setup()
        except RepoSetupError:
            pass
            print("Not a CoLRev repository.")
            return
        EnvironmentManager.register_repo(path_to_register=self.local_path)
        LOCAL_INDEX = LocalIndex()
        LOCAL_INDEX.index_colrev_project(repo_source_path=str(self.local_path))
        return


if __name__ == "__main__":
    pass
