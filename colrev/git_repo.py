#! /usr/bin/env python
"""Git repository wrapper for CoLRev"""
from __future__ import annotations

import time
import typing
from pathlib import Path
from random import randint

import git
from git import GitCommandError
from git import InvalidGitRepositoryError

import colrev.exceptions as colrev_exceptions
import colrev.utils
from colrev.constants import FileSets

if typing.TYPE_CHECKING:
    import colrev.review_manager

# pylint: disable=too-many-public-methods


class GitRepo:
    """Wrapper for Git repository interactions"""

    def __init__(self, path: typing.Optional[Path]) -> None:
        self.path = path if path else Path.cwd()
        if not self.path.is_absolute():
            self.path = self.path.resolve()
        self.path = colrev.utils.get_project_home_dir(path_str=str(self.path))
        try:
            self.repo = git.Repo(self.path)
        except InvalidGitRepositoryError as exc:
            msg = "Not a CoLRev/git repository. Run\n    colrev init"
            raise colrev_exceptions.RepoSetupError(msg) from exc

        self.update_gitignore(
            add=FileSets.DEFAULT_GIT_IGNORE_ITEMS,
            remove=FileSets.DEPRECATED_GIT_IGNORE_ITEMS,
        )

    def repo_initialized(self) -> bool:
        """Check whether the repository is initialized"""
        try:
            self.repo.head.commit
        except ValueError:
            return False
        return True

    def has_record_changes(self, *, change_type: str = "all") -> bool:
        """Check whether the records have changes"""
        return self.has_changes(
            Path(self.path / "data" / "records.bib"), change_type=change_type
        )

    def has_changes(self, relative_path: Path, *, change_type: str = "all") -> bool:
        """Check whether the relative path (or the git repository) has changes"""
        assert change_type in [
            "all",
            "staged",
            "unstaged",
        ], "Invalid change_type specified"
        try:
            bool(self.repo.head.commit)
        except ValueError:
            return True  # Repository has no commit

        diff_index = [item.a_path for item in self.repo.index.diff(None)]
        diff_head = [item.a_path for item in self.repo.head.commit.diff()]
        unstaged_changes = diff_index + self.repo.untracked_files

        path_str = str(relative_path).replace("\\", "/")

        if change_type == "all":
            path_changed = path_str in diff_index + diff_head
        elif change_type == "staged":
            path_changed = path_str in diff_head
        elif change_type == "unstaged":
            path_changed = path_str in unstaged_changes
        else:
            return False
        return path_changed

    def update_gitignore(
        self, *, add: typing.Optional[list] = None, remove: typing.Optional[list] = None
    ) -> None:
        """Update the gitignore file by adding or removing particular paths"""
        git_ignore_file = self.path / Path(".gitignore")
        if git_ignore_file.is_file():
            gitignore_content = git_ignore_file.read_text(encoding="utf-8")
        else:
            gitignore_content = ""
        ignored_items = gitignore_content.splitlines()
        if remove:
            ignored_items = [x for x in ignored_items if x not in remove]
        if add:
            ignored_items += [str(a) for a in add if str(a) not in ignored_items]
        with git_ignore_file.open("w", encoding="utf-8") as file:
            file.write("\n".join(ignored_items) + "\n")
        self.add_changes(git_ignore_file)

    def _sleep_util_git_unlocked(self) -> None:
        i = 0
        while (self.path / Path(".git/index.lock")).is_file():  # pragma: no cover
            i += 1
            time.sleep(randint(1, 50) * 0.1)  # nosec
            if i > 5:
                print("Waiting for previous git operation to complete")
            elif i > 30:
                raise colrev_exceptions.GitNotAvailableError()

    def add_changes(
        self, path: Path, *, remove: bool = False, ignore_missing: bool = False
    ) -> None:
        """Add changed file to git"""
        if path.is_absolute():
            path = path.relative_to(self.path)
        path_str = str(path).replace("\\", "/")

        self._sleep_util_git_unlocked()
        try:
            if remove:
                self.repo.index.remove([path_str])
            else:
                self.repo.index.add([path_str])
        except FileNotFoundError as exc:
            if not ignore_missing:
                raise exc

    def get_untracked_files(self) -> list[Path]:
        """Get the files that are untracked by git"""
        return [Path(x) for x in self.repo.untracked_files]

    def records_changed(self) -> bool:
        """Check whether the records were changed"""
        main_recs_changed = "data/records.bib" in [
            item.a_path for item in self.repo.index.diff(None)
        ] + [x.a_path for x in self.repo.head.commit.diff()]
        return main_recs_changed

    # pylint: disable=too-many-arguments
    def create_commit(
        self,
        *,
        msg: str,
        review_manager: colrev.review_manager.ReviewManager,
        manual_author: bool = False,
        script_call: str = "",
        saved_args: typing.Optional[dict] = None,
        skip_status_yaml: bool = False,
        skip_hooks: bool = True,
    ) -> bool:
        """Create a commit (including a commit report)"""
        # pylint: disable=import-outside-toplevel
        # pylint: disable=redefined-outer-name
        import colrev.ops.commit

        if review_manager.exact_call and script_call == "":
            script_call = review_manager.exact_call

        commit = colrev.ops.commit.Commit(
            review_manager=review_manager,
            msg=msg,
            manual_author=manual_author,
            script_name=script_call,
            saved_args=saved_args,
            skip_hooks=skip_hooks,
        )
        ret = commit.create(skip_status_yaml=skip_status_yaml)
        return ret

    def file_in_history(self, filepath: Path) -> bool:
        """Check whether a file is in the git history"""
        return str(filepath) in [o.path for o in self.repo.head.commit.tree.traverse()]

    def get_commit_message(self, *, commit_nr: int) -> str:
        """Get the commit message for commit #"""
        master = self.repo.head.reference
        assert commit_nr == 0  # extension : implement other cases
        if commit_nr == 0:
            cmsg = master.commit.message
            return cmsg
        return ""

    def add_setting_changes(self) -> None:
        """Add changes in settings to git"""
        self._sleep_util_git_unlocked()
        self.repo.index.add([str(self.path / "settings.json")])

    def has_untracked_search_records(self) -> bool:
        """Check whether there are untracked search records"""
        return any(
            str(Path("data/search")) in str(untracked_file)
            for untracked_file in self.get_untracked_files()
        )

    def stash_unstaged_changes(self) -> bool:
        """Stash unstaged changes"""
        ret = self.repo.git.stash("push", "--keep-index")
        return "No local changes to save" != ret

    def get_last_commit_sha(self) -> str:  # pragma: no cover
        """Get the last commit sha"""
        return str(self.repo.head.commit.hexsha)

    def get_tree_hash(self) -> str:  # pragma: no cover
        """Get the current tree hash"""
        tree_hash = self.repo.git.execute(["git", "write-tree"])
        return str(tree_hash)

    def get_last_updated(self, feed_file: Path) -> str:
        """Returns the date of the last update (if available) in YYYY-MM-DD format"""
        if not feed_file.is_file():
            return ""
        return self.get_last_commit_date(feed_file)

    def _get_remote_commit_differences(self) -> list:  # pragma: no cover
        origin = self.repo.remotes.origin
        if origin.exists():
            try:
                origin.fetch()
            except GitCommandError:
                return [-1, -1]

        nr_commits_behind, nr_commits_ahead = -1, -1
        if self.repo.active_branch.tracking_branch() is not None:
            branch_name = str(self.repo.active_branch)
            tracking_branch_name = str(self.repo.active_branch.tracking_branch())

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = self.repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for _ in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = self.repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for _ in commits_ahead)

        return [nr_commits_behind, nr_commits_ahead]

    def behind_remote(self) -> bool:  # pragma: no cover
        """Check whether the repository is behind the remote"""
        nr_commits_behind = 0
        connected_remote = 0 != len(self.repo.remotes)
        if connected_remote:
            origin = self.repo.remotes.origin
            if origin.exists():
                (
                    nr_commits_behind,
                    _,
                ) = self._get_remote_commit_differences()
        if nr_commits_behind > 0:
            return True
        return False

    def remote_ahead(self) -> bool:  # pragma: no cover
        """Check whether the remote is ahead"""
        connected_remote = 0 != len(self.repo.remotes)
        if connected_remote:
            origin = self.repo.remotes.origin
            if origin.exists():
                (
                    _,
                    nr_commits_ahead,
                ) = self._get_remote_commit_differences()
                if nr_commits_ahead > 0:
                    return True
        return False

    def pull_if_repo_clean(self) -> None:  # pragma: no cover
        """Pull project if repository is clean"""
        if not self.repo.is_dirty():
            origin = self.repo.remotes.origin
            origin.pull()

    def get_remote_url(self) -> str:  # pragma: no cover
        """Get the remote url"""
        remote_url = "NA"
        for remote in self.repo.remotes:
            if remote.name == "origin":
                remote_url = remote.url
        return remote_url

    def get_last_commit_date(self, filename: Path) -> str:
        """Get the last commit date for a file"""
        last_commit = next(self.repo.iter_commits(paths=filename))
        return last_commit.committed_datetime.isoformat()
