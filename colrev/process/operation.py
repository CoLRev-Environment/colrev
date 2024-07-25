#!/usr/bin/env python3
"""Types and model of CoLRev operations."""
from __future__ import annotations

import typing

import docker
import git
from docker.errors import DockerException

import colrev.exceptions as colrev_exceptions
from colrev.constants import OperationsType
from colrev.process.model import ProcessModel

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.review_manager

F = typing.TypeVar("F", bound=typing.Callable[..., typing.Any])


class Operation:
    """Operations correspond to the work steps in a CoLRev project"""

    type: OperationsType

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        operations_type: OperationsType,
        notify_state_transition_operation: bool = True,
    ) -> None:
        self.review_manager = review_manager
        self.type = operations_type
        self.notify_state_transition_operation = notify_state_transition_operation
        self.notify(state_transition=notify_state_transition_operation)
        self.cpus = 4
        self.docker_images_to_stop: typing.List[str] = []

        # Note: the following call seems to block the flow (if debug is enabled)
        # self.review_manager.logger.debug(f"Created {self.type} operation")

    # pylint: disable=too-many-nested-blocks
    @classmethod
    def decorate(cls) -> typing.Callable:
        """Decorator for operations"""

        def decorator_func(func: F) -> typing.Callable:
            def wrapper_func(self, *args, **kwargs) -> typing.Any:  # type: ignore
                # Invoke the wrapped function
                retval = func(self, *args, **kwargs)
                # Conclude the operation
                self.conclude()
                if self.review_manager.in_ci_environment():
                    print("\n\n")
                return retval

            return wrapper_func

        return decorator_func

    def conclude(self) -> None:  # pragma: no cover
        """Conclude the operation (stop Docker containers)"""
        try:
            client = docker.from_env()
            for container in client.containers.list():
                if any(x in container.image.tags for x in self.docker_images_to_stop):
                    container.stop()
        except DockerException:
            pass

    def _check_model_precondition(self) -> None:
        ProcessModel.check_operation_precondition(self)

    def _require_clean_repo_general(
        self,
        *,
        ignored_files: typing.Optional[list] = None,
    ) -> bool:

        # Note : not considering untracked files.
        git_repo = git.Repo(self.review_manager.path)

        # Principle: working tree always has to be clean
        # because processing functions may change content
        if git_repo.is_dirty(index=False):
            changed_files = [item.a_path for item in git_repo.index.diff(None)]
            raise colrev_exceptions.UnstagedGitChangesError(changed_files)

        if not git_repo.is_dirty():
            return True

        ignored_file_list = [str(self.review_manager.paths.STATUS_FILE)]
        if ignored_files:
            ignored_file_list += ignored_files
        ignored_file_list = [str(x).replace("\\", "/") for x in ignored_file_list]

        changed_files = [
            item.a_path
            for item in git_repo.index.diff(None)
            if not any(ip in item.a_path.replace("\\", "/") for ip in ignored_file_list)
        ] + [
            item.a_path
            for item in git_repo.head.commit.diff()
            if not any(ip in item.a_path.replace("\\", "/") for ip in ignored_file_list)
        ]

        if changed_files:
            raise colrev_exceptions.CleanRepoRequiredError(
                changed_files, ",".join(ignored_file_list)
            )

        return True  # pragma: no cover

    def check_precondition(self) -> None:
        """Check the operation precondition"""

        if self.review_manager.force_mode:
            return

        if self.type == OperationsType.load:
            self._require_clean_repo_general(
                ignored_files=[
                    self.review_manager.paths.SEARCH_DIR,
                    self.review_manager.paths.SETTINGS_FILE,
                ]
            )
            self._check_model_precondition()

        elif self.type == OperationsType.prep_man:  # pragma: no cover
            self._require_clean_repo_general(
                ignored_files=[self.review_manager.paths.RECORDS_FILE_GIT]
            )
            self._check_model_precondition()

        elif self.type in [
            OperationsType.prep,
            OperationsType.dedupe,
            OperationsType.prescreen,
            OperationsType.pdf_prep,
            OperationsType.screen,
        ]:
            self._require_clean_repo_general()
            self._check_model_precondition()

        elif self.type in [
            OperationsType.pdf_get,
            OperationsType.pdf_get_man,
        ]:
            self._require_clean_repo_general(
                ignored_files=[self.review_manager.paths.PDF_DIR]
            )
            self._check_model_precondition()

        elif self.type == OperationsType.data:
            self._check_model_precondition()

        # ie., implicit pass for check, pdf_prep_man

    def notify(self, *, state_transition: bool = True) -> None:
        """Notify the review_manager about the next operation"""

        self.review_manager.notified_next_operation = self.type
        if state_transition:
            self.check_precondition()
        if hasattr(self.review_manager, "dataset"):
            self.review_manager.dataset.reset_log_if_no_changes()
