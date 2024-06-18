#!/usr/bin/env python3
"""Functionality for data/records.bib and git repository."""
from __future__ import annotations

import os
import tempfile
import time
import typing
from pathlib import Path
from random import randint

import git
from git import GitCommandError
from git import InvalidGitRepositoryError

import colrev.exceptions as colrev_exceptions
import colrev.loader.bib
import colrev.loader.load_utils
import colrev.ops.check
import colrev.process.operation
import colrev.record.record
import colrev.record.record_id_setter
import colrev.record.record_prep
from colrev.constants import ExitCodes
from colrev.constants import Fields
from colrev.constants import FileSets
from colrev.constants import RecordState
from colrev.writer.write_utils import to_string

# pylint: disable=too-many-public-methods


class Dataset:
    """The CoLRev dataset (records and their history in git)"""

    _git_repo: git.Repo

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.review_manager = review_manager

        try:
            # In most cases, the repo should exist
            # due to review_manager._get_project_home_dir()
            self._git_repo = git.Repo(self.review_manager.path)
        except InvalidGitRepositoryError as exc:
            msg = "Not a CoLRev/git repository. Run\n    colrev init"
            raise colrev_exceptions.RepoSetupError(msg) from exc

        self.update_gitignore(
            add=FileSets.DEFAULT_GIT_IGNORE_ITEMS,
            remove=FileSets.DEPRECATED_GIT_IGNORE_ITEMS,
        )

    def update_gitignore(
        self, *, add: typing.Optional[list] = None, remove: typing.Optional[list] = None
    ) -> None:
        """Update the gitignore file by adding or removing particular paths"""
        # The following may print warnings...

        git_ignore_file = self.review_manager.paths.git_ignore
        if git_ignore_file.is_file():
            gitignore_content = git_ignore_file.read_text(encoding="utf-8")
        else:
            gitignore_content = ""
        ignored_items = gitignore_content.splitlines()
        if remove:
            ignored_items = [x for x in ignored_items if x not in remove]
        if add:
            ignored_items = ignored_items + [
                str(a) for a in add if str(a) not in ignored_items
            ]

        with git_ignore_file.open("w", encoding="utf-8") as file:
            file.write("\n".join(ignored_items) + "\n")
        self.add_changes(git_ignore_file)

    def get_origin_state_dict(self, records_string: str = "") -> dict:
        """Get the origin_state_dict (to determine state transitions efficiently)

        {'30_example_records.bib/Staehr2010': <RecordState.pdf_not_available: 10>,}
        """

        current_origin_states_dict = {}
        if records_string != "":
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".bib"
            ) as temp_file:
                temp_file.write(records_string.encode("utf-8"))
                temp_file_path = Path(temp_file.name)
            bib_loader = colrev.loader.bib.BIBLoader(
                filename=temp_file_path,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )
        else:
            bib_loader = colrev.loader.bib.BIBLoader(
                filename=self.review_manager.paths.records,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )
        for record_header_item in bib_loader.get_record_header_items().values():
            for origin in record_header_item[Fields.ORIGIN]:
                current_origin_states_dict[origin] = record_header_item[Fields.STATUS]
        return current_origin_states_dict

    def get_committed_origin_state_dict(self) -> dict:
        """Get the committed origin_state_dict"""
        revlist = (
            (
                commit.hexsha,
                (
                    commit.tree / self.review_manager.paths.RECORDS_FILE_GIT
                ).data_stream.read(),
            )
            for commit in self._git_repo.iter_commits(
                paths=self.review_manager.paths.RECORDS_FILE_GIT
            )
        )
        filecontents = list(revlist)[0][1]

        committed_origin_state_dict = self.get_origin_state_dict(
            filecontents.decode("utf-8")
        )
        return committed_origin_state_dict

    def load_records_from_history(self, commit_sha: str = "") -> typing.Iterator[dict]:
        """
        Iterates through Git history, yielding records file contents as dictionaries.

        Starts iteration from a provided commit SHA.
        Skips commits where the records file is unchanged.
        Useful for tracking dataset changes over time.

        Parameters:
            commit_sha (str, optional): Start iteration from this commit SHA.
            Defaults to beginning of Git history if not provided.

        Yields:
            dict: Records file contents at a specific Git history point, as a dictionary.
        """

        reached_target_commit = False  # if no commit_sha provided
        for current_commit in self._git_repo.iter_commits(
            paths=self.review_manager.paths.RECORDS_FILE_GIT
        ):

            # Skip all commits before the specified commit_sha, if provided
            if commit_sha and not reached_target_commit:
                if commit_sha != current_commit.hexsha:
                    # Move to the next commit
                    continue
                reached_target_commit = True

            # Read and parse the records file from the current commit
            filecontents = (
                current_commit.tree / self.review_manager.paths.RECORDS_FILE_GIT
            ).data_stream.read()

            records_dict = colrev.loader.load_utils.loads(
                load_string=filecontents.decode("utf-8", "replace"),
                implementation="bib",
                logger=self.review_manager.logger,
            )
            if records_dict:
                yield records_dict

    def load_records_dict(
        self,
        *,
        header_only: bool = False,
    ) -> dict:
        """Load the records

        header_only:

        {"Staehr2010": {'ID': 'Staehr2010',
        'colrev_origin': ['30_example_records.bib/Staehr2010'],
        'colrev_status': <RecordState.md_imported: 2>,
        'screening_criteria': 'criterion1=in;criterion2=out',
        'file': PosixPath('data/pdfs/Smith2000.pdf'),
        'colrev_data_provenance': {Fields.AUTHOR:{"source":"...", "note":"..."}}},
        }
        """

        if self.review_manager.notified_next_operation is None:
            raise colrev_exceptions.ReviewManagerNotNotifiedError()

        if header_only:
            # Note : currently not parsing screening_criteria to settings.ScreeningCriterion
            # to optimize performance
            bib_loader = colrev.loader.bib.BIBLoader(
                filename=self.review_manager.paths.records,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )
            return bib_loader.get_record_header_items()

        if self.review_manager.paths.records.is_file():

            records_dict = colrev.loader.load_utils.load(
                filename=self.review_manager.paths.records,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )

        else:
            records_dict = {}

        return records_dict

    def save_records_dict_to_file(self, records: dict) -> None:
        """Save the records dict"""
        # Note : this classmethod function can be called by CoLRev scripts
        # operating outside a CoLRev repo (e.g., sync)

        bibtex_str = to_string(records_dict=records, implementation="bib")

        with open(self.review_manager.paths.records, "w", encoding="utf-8") as out:
            out.write(bibtex_str + "\n")

        self._add_record_changes()

    def _save_record_list_by_id(self, records: dict) -> None:

        parsed = to_string(records_dict=records, implementation="bib")
        record_list = [
            {
                Fields.ID: item[item.find("{") + 1 : item.find(",")],
                "record": "@" + item + "\n",
            }
            for item in parsed.split("\n@")
        ]
        # Correct the first item
        record_list[0]["record"] = "@" + record_list[0]["record"][2:]

        current_id_str = "NOTSET"
        if self.review_manager.paths.records.is_file():
            with open(self.review_manager.paths.records, "r+b") as file:
                seekpos = file.tell()
                line = file.readline()
                while line:
                    if b"@" in line[:3]:
                        current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                        current_id_str = current_id.decode("utf-8")
                    if current_id_str in [x[Fields.ID] for x in record_list]:
                        replacement = [
                            x["record"]
                            for x in record_list
                            if x[Fields.ID] == current_id_str
                        ][0]
                        record_list = [
                            x for x in record_list if x[Fields.ID] != current_id_str
                        ]
                        line = file.readline()
                        while (
                            b"@" not in line[:3] and line
                        ):  # replace: drop the current record
                            line = file.readline()
                        remaining = line + file.read()
                        file.seek(seekpos)
                        file.write(replacement.encode("utf-8"))
                        seekpos = file.tell()
                        file.flush()
                        os.fsync(file)
                        file.write(remaining)
                        file.truncate()  # if the replacement is shorter...
                        file.seek(seekpos)

                    seekpos = file.tell()
                    line = file.readline()

        if len(record_list) > 0:
            with open(
                self.review_manager.paths.records, "a", encoding="utf8"
            ) as m_refs:
                for item in record_list:
                    m_refs.write(item["record"])

        self._add_record_changes()

    def save_records_dict(self, records: dict, *, partial: bool = False) -> None:
        """Save the records dict in RECORDS_FILE"""

        if partial:
            self._save_record_list_by_id(records)
            return
        self.save_records_dict_to_file(records)

    def read_next_record(self, *, conditions: list) -> typing.Iterator[dict]:
        """Read records (Iterator) based on condition"""

        # Note : matches conditions connected with 'OR'
        records = self.load_records_dict()

        records_list = []
        for _, record in records.items():
            for condition in conditions:
                for key, value in condition.items():
                    if str(value) == str(record[key]):
                        records_list.append(record)
        yield from records_list

    def format_records_file(self) -> dict:
        """Format the records file (Entrypoint for pre-commit hooks)"""

        if (
            not self.review_manager.paths.records.is_file()
            or not self.records_changed()
        ):
            return {"status": ExitCodes.SUCCESS, "msg": "Everything ok."}

        colrev.ops.check.CheckOperation(self.review_manager)  # to notify
        quality_model = self.review_manager.get_qm()
        records = self.load_records_dict()
        for record_dict in records.values():
            if Fields.STATUS not in record_dict:
                return {
                    "status": ExitCodes.FAIL,
                    "msg": f" no status field in record ({record_dict[Fields.ID]})",
                }

            record = colrev.record.record_prep.PrepRecord(record_dict)
            if record_dict[Fields.STATUS] in [
                RecordState.md_needs_manual_preparation,
            ]:
                record.run_quality_model(quality_model, set_prepared=True)

            if record_dict[Fields.STATUS] == RecordState.pdf_prepared:
                record.reset_pdf_provenance_notes()

        self.save_records_dict(records)
        changed = self.review_manager.paths.RECORDS_FILE in [
            r.a_path for r in self._git_repo.index.diff(None)
        ]
        self.review_manager.update_status_yaml()
        self.review_manager.load_settings()
        self.review_manager.save_settings()

        if changed:  # pragma: no cover
            return {"status": ExitCodes.FAIL, "msg": "Records formatted"}

        return {"status": ExitCodes.SUCCESS, "msg": "Everything ok."}

    # ID creation, update and lookup ---------------------------------------

    def propagated_id(self, *, record_id: str) -> bool:
        """Check whether an ID is propagated (i.e., its record's status is beyond md_processed)"""

        for record in self.load_records_dict(header_only=True).values():
            if record[Fields.ID] == record_id:
                if record[Fields.STATUS] in RecordState.get_post_x_states(
                    state=RecordState.md_processed
                ):
                    return True

        return False

    def set_ids(self, selected_ids: typing.Optional[list] = None) -> dict:
        """Set the IDs of records according to predefined formats or
        according to the LocalIndex"""
        id_setter = colrev.record.record_id_setter.IDSetter(
            id_pattern=self.review_manager.settings.project.id_pattern,
            skip_local_index=self.review_manager.settings.is_curated_masterdata_repo(),
        )
        records = self.load_records_dict()
        updated_records = id_setter.set_ids(
            records=records,
            selected_ids=selected_ids,
        )
        self.save_records_dict(records)
        self.add_changes(self.review_manager.paths.RECORDS_FILE)
        return updated_records

    # GIT operations -----------------------------------------------

    def get_repo(self) -> git.Repo:
        """Get the git repository object"""

        if self.review_manager.notified_next_operation is None:
            raise colrev_exceptions.ReviewManagerNotNotifiedError()
        return self._git_repo

    def repo_initialized(self) -> bool:
        """Check whether the repository is initialized"""
        try:
            self._git_repo.head.commit
        except ValueError:
            return False
        return True

    def has_record_changes(self, *, change_type: str = "all") -> bool:
        """Check whether the records have changes"""
        return self.has_changes(
            Path(self.review_manager.paths.RECORDS_FILE_GIT), change_type=change_type
        )

    def has_changes(self, relative_path: Path, *, change_type: str = "all") -> bool:
        """Check whether the relative path (or the git repository) has changes"""

        assert change_type in [
            "all",
            "staged",
            "unstaged",
        ], "Invalid change_type specified"

        # Check if the repository has at least one commit
        try:
            bool(self._git_repo.head.commit)
        except ValueError:
            return True  # Repository has no commit

        diff_index = [item.a_path for item in self._git_repo.index.diff(None)]
        diff_head = [item.a_path for item in self._git_repo.head.commit.diff()]
        unstaged_changes = diff_index + self._git_repo.untracked_files

        # Ensure the path uses forward slashes, which is compatible with Git's path handling
        path_str = str(relative_path).replace("\\", "/")

        if change_type == "all":
            path_changed = path_str in diff_index + diff_head
        elif change_type == "staged":
            path_changed = path_str in diff_head
        elif change_type == "unstaged":
            path_changed = path_str in unstaged_changes
        return path_changed

    def _sleep_util_git_unlocked(self) -> None:
        i = 0
        while (
            self.review_manager.path / Path(".git/index.lock")
        ).is_file():  # pragma: no cover
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
            path = path.relative_to(self.review_manager.path)
        path_str = str(path).replace("\\", "/")

        self._sleep_util_git_unlocked()
        try:
            if remove:
                self._git_repo.index.remove([path_str])
            else:
                self._git_repo.index.add([path_str])
        except FileNotFoundError as exc:
            if not ignore_missing:
                raise exc

    def get_untracked_files(self) -> list:
        """Get the files that are untracked by git"""

        return [Path(x) for x in self._git_repo.untracked_files]

    def records_changed(self) -> bool:
        """Check whether the records were changed"""
        main_recs_changed = self.review_manager.paths.RECORDS_FILE_GIT in [
            item.a_path for item in self._git_repo.index.diff(None)
        ] + [x.a_path for x in self._git_repo.head.commit.diff()]
        return main_recs_changed

    # pylint: disable=too-many-arguments
    def create_commit(
        self,
        *,
        msg: str,
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

        if self.review_manager.exact_call and script_call == "":
            script_call = self.review_manager.exact_call

        commit = colrev.ops.commit.Commit(
            review_manager=self.review_manager,
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
        return str(filepath) in [
            o.path for o in self._git_repo.head.commit.tree.traverse()
        ]

    def get_commit_message(self, *, commit_nr: int) -> str:
        """Get the commit message for commit #"""
        master = self._git_repo.head.reference
        assert commit_nr == 0  # extension : implement other cases
        if commit_nr == 0:
            cmsg = master.commit.message
        return cmsg

    def _add_record_changes(self) -> None:
        """Add changes in records to git"""
        self._sleep_util_git_unlocked()
        self._git_repo.index.add([str(self.review_manager.paths.RECORDS_FILE)])

    def add_setting_changes(self) -> None:
        """Add changes in settings to git"""
        self._sleep_util_git_unlocked()

        self._git_repo.index.add([str(self.review_manager.paths.SETTINGS_FILE)])

    def has_untracked_search_records(self) -> bool:
        """Check whether there are untracked search records"""
        return any(
            str(self.review_manager.paths.SEARCH_DIR) in str(untracked_file)
            for untracked_file in self.get_untracked_files()
        )

    def stash_unstaged_changes(self) -> bool:
        """Stash unstaged changes"""
        ret = self._git_repo.git.stash("push", "--keep-index")
        return "No local changes to save" != ret

    def reset_log_if_no_changes(self) -> None:
        """Reset the report log file if there are not changes"""
        if not self._git_repo.is_dirty():
            self.review_manager.reset_report_logger()

    def get_last_commit_sha(self) -> str:  # pragma: no cover
        """Get the last commit sha"""
        return str(self._git_repo.head.commit.hexsha)

    def get_tree_hash(self) -> str:  # pragma: no cover
        """Get the current tree hash"""
        tree_hash = self._git_repo.git.execute(["git", "write-tree"])
        return str(tree_hash)

    def _get_remote_commit_differences(self) -> list:  # pragma: no cover
        origin = self._git_repo.remotes.origin
        if origin.exists():
            try:
                origin.fetch()
            except GitCommandError:
                return [-1, -1]

        nr_commits_behind, nr_commits_ahead = -1, -1
        if self._git_repo.active_branch.tracking_branch() is not None:
            branch_name = str(self._git_repo.active_branch)
            tracking_branch_name = str(self._git_repo.active_branch.tracking_branch())
            # self.review_manager.logger.debug(f"{branch_name} - {tracking_branch_name}")

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = self._git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = self._git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

        return [nr_commits_behind, nr_commits_ahead]

    def behind_remote(self) -> bool:  # pragma: no cover
        """Check whether the repository is behind the remote"""
        nr_commits_behind = 0
        connected_remote = 0 != len(self._git_repo.remotes)
        if connected_remote:
            origin = self._git_repo.remotes.origin
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
        connected_remote = 0 != len(self._git_repo.remotes)
        if connected_remote:
            origin = self._git_repo.remotes.origin
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
        if not self._git_repo.is_dirty():
            origin = self._git_repo.remotes.origin
            origin.pull()

    def get_remote_url(self) -> str:  # pragma: no cover
        """Get the remote url"""
        remote_url = "NA"
        for remote in self._git_repo.remotes:
            if remote.name == "origin":
                remote_url = remote.url
        return remote_url
