#! /usr/bin/env python
"""CoLRev pull operation: Pull project and records."""
from __future__ import annotations

import colrev.process.operation
from colrev.constants import Colors
from colrev.constants import OperationsType

# pylint: disable=too-few-public-methods

CHANGE_COUNTER = None


class Pull(colrev.process.operation.Operation):
    """Pull the project and records"""

    type = OperationsType.format

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
        )

    @colrev.process.operation.Operation.decorate()
    def main(self) -> None:
        """Pull the CoLRev project and records (main entrypoint)"""

        self._pull_project()

    def _pull_project(self) -> None:
        try:
            git_repo = self.review_manager.dataset.get_repo()
            origin = git_repo.remotes.origin
            self.review_manager.logger.info(
                f"Pull project changes from {git_repo.remotes.origin}"
            )
            res = origin.pull()
        except AttributeError:
            self.review_manager.logger.info(
                f"{Colors.RED}No remote detected for pull{Colors.END}"
            )
            return

        if 4 == res[0].flags:
            self.review_manager.logger.info(
                f"{Colors.GREEN}Project up-to-date{Colors.END}"
            )
        elif 64 == res[0].flags:
            self.review_manager.logger.info(
                f"{Colors.GREEN}Updated CoLRev repository{Colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f"{Colors.RED}Returned flag {res[0].flags}{Colors.END}"
            )
        print()
