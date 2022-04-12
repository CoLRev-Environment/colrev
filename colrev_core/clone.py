#! /usr/bin/env python
import os
from pathlib import Path

from colrev_core.environment import EnvironmentManager
from colrev_core.environment import LocalIndex
from colrev_core.review_manager import RepoSetupError
from colrev_core.review_manager import ReviewManager


class Clone:
    def __init__(self, git_url):
        self.git_url = git_url

        git_repo_name = git_url[git_url.rfind("/") + 1 :]
        self.local_path = Path.cwd() / Path(git_repo_name)

        if self.pull_git_repo(git_url, self.local_path):
            os.chdir(str(self.local_path))
            try:
                REVIEW_MANAGER = ReviewManager(str(self.local_path))
                REVIEW_MANAGER.check_repository_setup()
            except RepoSetupError:
                pass
                print("Not a CoLRev repository.")
                return
            EnvironmentManager.register_repo(self.local_path)
            LOCAL_INDEX = LocalIndex()
            LOCAL_INDEX.index_colrev_project(str(self.local_path))
        else:
            print("Clone of repository failed")

    def pull_git_repo(self, git_url: str, repo_dir: Path) -> bool:
        from git import Repo

        Repo.clone_from(git_url, str(repo_dir))
        return True


if __name__ == "__main__":
    pass
