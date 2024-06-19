#!/usr/bin/env python3
"""Create a commit, including the CoLRev report."""
from __future__ import annotations

import importlib
import os
import sys
import typing
from importlib.metadata import version
from pathlib import Path

import git
import gitdb.exc

import colrev.env.utils
import colrev.exceptions as colrev_exceptions

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.review_manager
    import colrev.ops.status


class Commit:
    """Create commits"""

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments

    ext_script_name: str
    ext_script_version: str
    python_version: str
    git_version: str
    docker_version: str
    last_commit_sha: str
    tree_hash: str
    records_committed: bool
    completeness_condition: bool
    # Note: last_commit_sha and tree_hash are used in the commit message (external template)

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        msg: str,
        manual_author: bool,
        script_name: str,
        saved_args: typing.Optional[dict] = None,
        skip_hooks: bool = False,
    ) -> None:
        self.review_manager = review_manager
        self.msg = msg
        self.manual_author = manual_author
        self.script_name = self._parse_script_name(script_name)
        self.saved_args = self._parse_saved_args(saved_args)
        self.skip_hooks = skip_hooks

        self._set_versions()
        self._set_script_information(script_name)

    def _parse_script_name(self, script_name: str) -> str:
        if script_name == "MANUAL":
            script_name = "Commit created manually or by external script"
        elif " " in script_name:
            script_name = script_name.replace("colrev cli", "colrev").replace(
                "prescreen_cli", "prescreen"
            )
        return script_name

    def _parse_saved_args(self, saved_args: typing.Optional[dict] = None) -> str:
        saved_args_str = ""
        if saved_args is not None:
            for key, value in saved_args.items():
                if isinstance(value, (bool, float, int, str)):
                    if value == "":  # pragma: no cover
                        saved_args_str += f"     --{key} \\\n"
                    else:
                        saved_args_str += f"     --{key}={value} \\\n"
            # Replace the last backslash (for argument chaining across linebreaks)
            saved_args_str = saved_args_str.rstrip(" \\\n")
        return saved_args_str

    def _set_versions(self) -> None:
        self.colrev_version = f'version {version("colrev")}'
        sys_v = sys.version
        self.python_version = f'version {sys_v[: sys_v.find(" ")]}'
        stream = os.popen("git --version")
        self.git_version = stream.read().replace("git ", "").replace("\n", "")
        stream = os.popen("docker --version")
        self.docker_version = stream.read().replace("Docker ", "").replace("\n", "")
        if self.docker_version == "":  # pragma: no cover
            self.docker_version = "Not installed"

    def _set_script_information(self, script_name: str) -> None:
        self.ext_script_name = ""
        self.ext_script_version = ""

        if script_name == "":
            return

        # Note : the script_name / ext_script seems to be different on macos during init!?
        ext_script = script_name.split(" ")[0]
        if ext_script != "colrev":
            try:
                script_version = version(ext_script)
                self.ext_script_name = script_name
                self.ext_script_version = f"version {script_version}"
            except importlib.metadata.PackageNotFoundError:
                pass
            except ValueError:  # pragma: no cover
                # Note : macos error in importlib.metadata.version
                # ValueError: A distribution name is required
                self.ext_script_name = "unknown"
                self.ext_script_version = "unknown"

    def _get_version_flag(self) -> str:
        flag = ""
        if "dirty" in version("colrev"):  # pragma: no cover
            flag = "*"
        return flag

    def _get_commit_report(self, status_operation: colrev.ops.status.Status) -> str:
        report = self._get_commit_report_header()
        report += status_operation.get_review_status_report(colors=False)
        report += self._get_commit_report_details()
        return report

    def _get_commit_report_header(self) -> str:
        template = colrev.env.utils.get_template("ops/commit/commit_report_header.txt")
        content = template.render(commit_details=self)
        return content

    def _get_commit_report_details(self) -> str:
        template = colrev.env.utils.get_template("ops/commit/commit_report_details.txt")
        content = template.render(commit_details=self)
        return content

    def _get_detailed_processing_report(self) -> str:
        processing_report = ""
        report_path = self.review_manager.paths.report
        if report_path.is_file():
            processing_report = "\nProcessing report\n"
            processing_report += "".join(report_path.read_text())
        return processing_report

    def create(self, *, skip_status_yaml: bool = False) -> bool:
        """Create a commit (including the commit message and details)"""
        status_operation = self.review_manager.get_status_operation()
        git_repo = self.review_manager.dataset.get_repo()
        try:
            if not git_repo.index.diff("HEAD"):
                self.review_manager.logger.debug(
                    "No staged changes / cannot create commit"
                )
                return False
        except gitdb.exc.BadName:
            self.review_manager.logger.debug(
                "HEAD does not exist, cannot create commit"
            )

        self.review_manager.logger.debug("Prepare commit: checks and updates")
        if not skip_status_yaml:
            status_yml = self.review_manager.paths.status
            self.review_manager.update_status_yaml()
            self.review_manager.dataset.add_changes(status_yml)

        committer, email = self.review_manager.get_committer()

        if self.manual_author:
            git_author = git.Actor(committer, email)
        else:
            git_author = git.Actor(f"script:{self.script_name}", email)

        # Note : this should run as the last command before creating the commit
        # to ensure that the git tree_hash is up-to-date.
        self.tree_hash = self.review_manager.dataset.get_tree_hash()
        try:
            self.last_commit_sha = self.review_manager.dataset.get_last_commit_sha()
        except ValueError:
            pass

        self.records_committed = self.review_manager.paths.records.is_file()
        self.completeness_condition = self.review_manager.get_completeness_condition()

        self.msg = (
            self.msg
            + self._get_version_flag()
            + self._get_commit_report(status_operation)
            + self._get_detailed_processing_report()
        )
        git_repo.index.commit(
            self.msg,
            author=git_author,
            committer=git.Actor(committer, email),
            skip_hooks=self.skip_hooks,
        )

        self.review_manager.logger.info("Created commit")
        self.review_manager.reset_report_logger()

        if self.review_manager.dataset.has_record_changes():
            if not self.review_manager.force_mode:
                raise colrev_exceptions.DirtyRepoAfterProcessingError(
                    "A clean repository is expected."
                )
            self.review_manager.logger.warning("No clean repository after commit.")

        return True

    def update_report(self, *, msg_file: Path) -> None:
        """Update the report"""
        status_operation = self.review_manager.get_status_operation()
        report = self._get_commit_report(status_operation)
        with open(msg_file, "a", encoding="utf8") as file:
            file.write(report)
