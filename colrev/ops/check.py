#!/usr/bin/env python3
"""Check operation."""
from __future__ import annotations

import typing

import colrev.process.operation
from colrev.constants import OperationsType


if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.review_manager


class CheckOperation(colrev.process.operation.Operation):
    """A dummy operation that is not expected to introduce changes"""

    # pylint: disable=too-few-public-methods

    type = OperationsType.check

    def __init__(self, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=False,
        )
