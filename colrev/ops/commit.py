#!/usr/bin/env python3
"""Create a commit, including the CoLRev report."""
from __future__ import annotations

import importlib
import os
import shutil
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Optional

import git

import colrev.env.utils
import colrev.exceptions as colrev_exceptions

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager


class Commit:
    """Create commits"""

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods

    __temp_path = Path.home().joinpath("colrev") / Path(".colrev_temp")

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        msg: str,
        manual_author: bool,
        script_name: str,
        saved_args: Optional[dict] = None,
    ) -> None:
        self.review_manager = review_manager
        self.manual_author = manual_author

        self.msg = msg
        self.script_name = self.__parse_script_name(script_name=script_name)
        self.saved_args = self.__parse_saved_args(saved_args=saved_args)
        self.tree_hash = ""

        self.last_commit_sha = ""
        try:
            self.last_commit_sha = review_manager.dataset.get_last_commit_sha()
        except ValueError:
            pass

        self.records_committed = review_manager.dataset.records_file.is_file()
        self.completeness_condition = review_manager.get_completeness_condition()
        self.colrev_version = f'version {version("colrev")}'
        sys_v = sys.version
        self.python_version = f'version {sys_v[: sys_v.find(" ")]}'
        stream = os.popen("git --version")
        self.git_version = stream.read().replace("git ", "").replace("\n", "")
        stream = os.popen("docker --version")
        self.docker_version = stream.read().replace("Docker ", "").replace("\n", "")
        if self.docker_version == "":
            self.docker_version = "Not installed"

        self.ext_script_name = ""
        self.ext_script_version = ""

        if script_name != "":
            ext_script = script_name.split(" ")[0]
            if ext_script != "colrev":
                try:
                    script_version = version(ext_script)
                    self.ext_script_name = script_name
                    self.ext_script_version = f"version {script_version}"
                except importlib.metadata.PackageNotFoundError:
                    pass
        self.__temp_path.mkdir(exist_ok=True, parents=True)

    def __parse_saved_args(self, *, saved_args: Optional[dict] = None) -> str:
        saved_args_str = ""
        if saved_args is not None:
            for key, value in saved_args.items():
                if isinstance(value, (bool, float, int, str)):
                    if value == "":
                        saved_args_str = saved_args_str + f"     --{key} \\\n"
                    else:
                        saved_args_str = saved_args_str + f"     --{key}={value} \\\n"
            # Replace the last backslash (for argument chaining across linebreaks)
            saved_args_str = saved_args_str.rstrip(" \\\n")

        return saved_args_str

    def __parse_script_name(self, *, script_name: str) -> str:
        if script_name == "MANUAL":
            script_name = "Commit created manually or by external script"
        elif " " in script_name:
            script_name = script_name.replace("colrev cli", "colrev").replace(
                "prescreen_cli", "prescreen"
            )
        return script_name

    def __get_version_flag(self) -> str:
        flag = ""
        if "dirty" in version("colrev"):
            flag = "*"
        return flag

    def __get_commit_report_header(self) -> str:
        template = colrev.env.utils.get_template(
            template_path="template/ops/commit_report_header.txt"
        )
        content = template.render(commit_details=self)

        return content

    def __get_commit_report_details(self) -> str:
        template = colrev.env.utils.get_template(
            template_path="template/ops/commit_report_details.txt"
        )
        content = template.render(commit_details=self)

        return content

    def __get_detailed_processing_report(self) -> str:
        processing_report = ""
        if self.review_manager.report_path.is_file():
            # Reformat
            prefixes = [
                "[('change', 'author',",
                "[('change', 'title',",
                "[('change', 'journal',",
                "[('change', 'booktitle',",
            ]

            with tempfile.NamedTemporaryFile(
                dir=self.__temp_path, mode="r+b", delete=False
            ) as temp:
                with open(self.review_manager.report_path, "r+b") as file:
                    shutil.copyfileobj(file, temp)  # type: ignore
            # self.report_path.rename(temp.name)
            with open(temp.name, encoding="utf8") as reader, open(
                self.review_manager.report_path, "w", encoding="utf8"
            ) as writer:
                line = reader.readline()
                while line:
                    if (
                        any(prefix in line for prefix in prefixes)
                        and "', '" in line[30:]
                    ):
                        split_pos = line.rfind("', '") + 2
                        indent = line.find("', (") + 3
                        writer.write(line[:split_pos] + "\n")
                        writer.write(" " * indent + line[split_pos:])
                    else:
                        writer.write(line)

                    line = reader.readline()

            with open(self.review_manager.report_path, encoding="utf8") as file:
                line = file.readline()
                debug_part = False
                while line:
                    # For more efficient debugging (loading of dict with Enum)
                    if "colrev_status" in line and "<RecordState." in line:
                        line = line.replace("<RecordState", "RecordState")
                        line = line[: line.rfind(":")] + line[line.rfind(">") + 1 :]
                    if "[DEBUG]" in line or debug_part:
                        debug_part = True
                        if any(
                            x in line
                            for x in ["[INFO]", "[ERROR]", "[WARNING]", "[CRITICAL"]
                        ):
                            debug_part = False
                    if not debug_part:
                        processing_report = processing_report + line
                    line = file.readline()

            processing_report = "\nProcessing report\n" + "".join(processing_report)
        return processing_report

    def __get_commit_report(self) -> str:
        status_operation = self.review_manager.get_status_operation()

        report = self.__get_commit_report_header()
        report += status_operation.get_review_status_report(colors=False)
        report += self.__get_commit_report_details()

        return report

    def create(self, *, skip_status_yaml: bool = False) -> bool:
        """Create a commit (including the commit message and details)"""

        if self.review_manager.dataset.has_changes():
            self.review_manager.logger.debug("Prepare commit: checks and updates")
            if not skip_status_yaml:
                self.review_manager.update_status_yaml()
                self.review_manager.dataset.add_changes(
                    path=self.review_manager.STATUS_RELATIVE
                )

            committer, email = self.review_manager.get_committer()

            if self.manual_author:
                git_author = git.Actor(committer, email)
            else:
                git_author = git.Actor(f"script:{self.script_name}", email)

            # Note : this should run as the last command before creating the commit
            # to ensure that the git tree_hash is up-to-date.
            self.tree_hash = self.review_manager.dataset.get_tree_hash()
            self.msg = (
                self.msg
                + self.__get_version_flag()
                + self.__get_commit_report()
                + self.__get_detailed_processing_report()
            )
            self.review_manager.dataset.create_commit(
                msg=self.msg,
                author=git_author,
                committer=git.Actor(committer, email),
                hook_skipping=True,
            )

            self.review_manager.logger.info("Created commit")
            self.review_manager.reset_report_logger()
            if self.review_manager.dataset.has_changes():
                raise colrev_exceptions.DirtyRepoAfterProcessingError(
                    "A clean repository is expected."
                )
            return True

        return False

    def update_report(self, *, msg_file: Path) -> None:
        """Update the report"""
        report = self.__get_commit_report()
        with open(msg_file, "a", encoding="utf8") as file:
            file.write(report)


if __name__ == "__main__":
    pass
