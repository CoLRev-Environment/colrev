#!/usr/bin/env python3
"""Types and model of CoLRev operations."""
from __future__ import annotations

from enum import auto
from enum import Enum
from typing import TYPE_CHECKING

import git

import colrev.exceptions as colrev_exceptions
import colrev.record

if TYPE_CHECKING:
    import colrev.review_manager


class OperationsType(Enum):
    # pylint: disable=invalid-name

    search = auto()
    load = auto()
    prep = auto()
    prep_man = auto()
    dedupe = auto()
    prescreen = auto()
    pdf_get = auto()
    pdf_get_man = auto()
    pdf_prep = auto()
    pdf_prep_man = auto()
    screen = auto()
    data = auto()

    format = auto()
    explore = auto()
    check = auto()

    def __str__(self) -> str:
        return f"{self.name}"


class Operation:
    # pylint: disable=too-few-public-methods

    force_mode: bool
    type: OperationsType

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        operations_type: OperationsType,
        notify_state_transition_operation: bool = True,
        debug: bool = False,
    ) -> None:

        self.review_manager = review_manager
        self.force_mode = self.review_manager.force_mode

        self.type = operations_type

        self.notify_state_transition_operation = notify_state_transition_operation
        if notify_state_transition_operation:
            self.review_manager.notify(operation=self)
        else:
            self.review_manager.notify(operation=self, state_transition=False)

        self.review_manager.debug_mode = debug

        self.cpus = 4

        # Note: the following call seems to block the flow (if debug is enabled)
        # self.review_manager.logger.debug(f"Created {self.type} operation")

        # Note: we call review_manager.notify() in the subclasses
        # to make sure that the review_manager calls the right check_preconditions()

    def check_record_state_model_precondition(self) -> None:
        record_state_model = colrev.record.RecordStateModel(
            operation=self.type, review_manager=self.review_manager
        )
        record_state_model.check_operation_precondition(operation=self)

    def require_clean_repo_general(
        self, *, git_repo: git.Repo = None, ignore_pattern: list = None
    ) -> bool:

        if git_repo is None:
            git_repo = git.Repo(self.review_manager.path)

        # Note : not considering untracked files.

        if len(git_repo.index.diff("HEAD")) == 0:
            unstaged_changes = [item.a_path for item in git_repo.index.diff(None)]
            if self.review_manager.dataset.RECORDS_FILE_RELATIVE in unstaged_changes:
                git_repo.index.add([self.review_manager.dataset.RECORDS_FILE_RELATIVE])

        # Principle: working tree always has to be clean
        # because processing functions may change content
        if git_repo.is_dirty(index=False):
            changed_files = [item.a_path for item in git_repo.index.diff(None)]
            raise colrev_exceptions.UnstagedGitChangesError(changed_files)

        if git_repo.is_dirty():
            if ignore_pattern is None:
                changed_files = [item.a_path for item in git_repo.index.diff(None)] + [
                    x.a_path
                    for x in git_repo.head.commit.diff()
                    if x.a_path not in [str(self.review_manager.STATUS_RELATIVE)]
                ]
                if len(changed_files) > 0:
                    raise colrev_exceptions.CleanRepoRequiredError(changed_files, "")
            else:
                changed_files = [
                    item.a_path
                    for item in git_repo.index.diff(None)
                    if not any(str(ip) in item.a_path for ip in ignore_pattern)
                ] + [
                    x.a_path
                    for x in git_repo.head.commit.diff()
                    if not any(str(ip) in x.a_path for ip in ignore_pattern)
                ]
                if str(self.review_manager.STATUS_RELATIVE) in changed_files:
                    changed_files.remove(str(self.review_manager.STATUS_RELATIVE))
                if changed_files:
                    raise colrev_exceptions.CleanRepoRequiredError(
                        changed_files, ",".join([str(x) for x in ignore_pattern])
                    )
        return True

    def check_precondition(self) -> None:
        """Check the operation precondition"""

        if (
            self.force_mode
            or "realtime" == self.review_manager.settings.project.review_type
        ):
            return

        if OperationsType.load == self.type:
            self.require_clean_repo_general(
                ignore_pattern=[
                    self.review_manager.SEARCHDIR_RELATIVE,
                    self.review_manager.SETTINGS_RELATIVE,
                ]
            )
            self.check_record_state_model_precondition()

        elif OperationsType.prep == self.type:

            if self.notify_state_transition_operation:
                self.require_clean_repo_general()
                self.check_record_state_model_precondition()

        elif OperationsType.prep_man == self.type:
            self.require_clean_repo_general(
                ignore_pattern=[self.review_manager.dataset.RECORDS_FILE_RELATIVE]
            )
            self.check_record_state_model_precondition()

        elif OperationsType.dedupe == self.type:
            self.require_clean_repo_general()
            self.check_record_state_model_precondition()

        elif OperationsType.prescreen == self.type:
            self.require_clean_repo_general(
                ignore_pattern=[self.review_manager.dataset.RECORDS_FILE_RELATIVE]
            )
            self.check_record_state_model_precondition()

        elif OperationsType.pdf_get == self.type:
            self.require_clean_repo_general(
                ignore_pattern=[self.review_manager.PDF_DIR_RELATIVE]
            )
            self.check_record_state_model_precondition()

        elif OperationsType.pdf_get_man == self.type:
            self.require_clean_repo_general(
                ignore_pattern=[self.review_manager.PDF_DIR_RELATIVE]
            )
            self.check_record_state_model_precondition()

        elif OperationsType.pdf_prep == self.type:
            self.require_clean_repo_general()
            self.check_record_state_model_precondition()

        elif OperationsType.screen == self.type:
            self.require_clean_repo_general()
            self.check_record_state_model_precondition()

        elif OperationsType.data == self.type:
            # require_clean_repo_general(
            #     ignore_pattern=[
            #         # data.csv, paper.md etc.?,
            #     ]
            # )
            self.check_record_state_model_precondition()

        # ie., implicit pass for format, explore, check, pdf_prep_man


class FormatOperation(Operation):
    # pylint: disable=too-few-public-methods

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager, operations_type=OperationsType.format
        )
        if notify:
            self.review_manager.notify(operation=self)


class CheckOperation(Operation):
    # pylint: disable=too-few-public-methods

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=OperationsType.check,
            notify_state_transition_operation=False,
        )


if __name__ == "__main__":
    pass
