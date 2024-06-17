#! /usr/bin/env python
"""Traces records and changes through history."""
from __future__ import annotations

import time
import typing

import dictdiffer

import colrev.process.operation
from colrev.constants import Colors
from colrev.constants import OperationsType

if typing.TYPE_CHECKING:  # pragma: no cover
    import git.objects.commit


class Trace(colrev.process.operation.Operation):
    """Trace a record through history"""

    type = OperationsType.check

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
        )

    def _print_diff(self, *, diff: dict, color: str, lpad: int = 5) -> None:
        formatted_diff = self.review_manager.p_printer.pformat(diff)
        lines = formatted_diff.splitlines()
        print(
            color
            + "\n".join(["".join([" " * lpad]) + line for line in lines])
            + Colors.END
        )

    def _print_record_changes(
        self,
        *,
        commit: git.objects.commit.Commit,
        records_dict: dict,
        record_id: str,
        prev_record: dict,
    ) -> dict:
        record = records_dict[record_id]

        diffs = list(dictdiffer.diff(prev_record, record))

        if len(diffs) > 0:
            if not self.review_manager.verbose_mode:  # pragma: no cover
                commit_message_first_line = str(commit.message).partition("\n")[0]
                print(
                    "\n\n"
                    + time.strftime(
                        "%Y-%m-%d %H:%M",
                        time.gmtime(commit.committed_date),
                    )
                    + f" {commit} ".ljust(40, " ")
                    + f" {commit_message_first_line} (by {commit.author.name})"
                )

            for diff in diffs:
                if diff[0] == "add":
                    self._print_diff(diff=diff, color=Colors.GREEN)
                if diff[0] == "change":
                    self._print_diff(diff=diff, color=Colors.ORANGE)
                if diff[0] == "delete":  # pragma: no cover
                    self._print_diff(diff=diff, color=Colors.RED)

        prev_record = record
        return prev_record

    @colrev.process.operation.Operation.decorate()
    def main(self, *, record_id: str) -> None:
        """Trace a record (main entrypoint)"""

        self.review_manager.logger.info(f"Trace record by ID: {record_id}")
        # Ensure the path uses forward slashes, which is compatible with Git's path handling

        revlist = self.review_manager.dataset.get_repo().iter_commits(
            paths=self.review_manager.paths.RECORDS_FILE_GIT
        )

        prev_record: dict = {}
        for commit in reversed(list(revlist)):
            filecontents = (
                commit.tree / self.review_manager.paths.RECORDS_FILE_GIT
            ).data_stream.read()
            commit_message_first_line = str(commit.message).partition("\n")[0]

            if self.review_manager.verbose_mode:
                print(
                    "\n\n"
                    + time.strftime(
                        "%Y-%m-%d %H:%M",
                        time.gmtime(commit.committed_date),
                    )
                    + f" {commit} ".ljust(40, " ")
                    + f" {commit_message_first_line} (by {commit.author.name})"
                )

            records_dict = colrev.loader.load_utils.loads(
                load_string=filecontents.decode("utf-8"),
                implementation="bib",
                logger=self.review_manager.logger,
            )

            if record_id not in records_dict:
                if self.review_manager.verbose_mode:
                    print(f"record {record_id} not in commit.")
                continue

            prev_record = self._print_record_changes(
                commit=commit,
                records_dict=records_dict,
                record_id=record_id,
                prev_record=prev_record,
            )
