#!/usr/bin/env python3
"""Linter for CoLRev - direct status assignment"""
from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes
from pylint import checkers
from pylint.checkers.utils import only_required_for_messages

from colrev.constants import Fields

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class DirectStatusAssignmentChecker(checkers.BaseChecker):
    """DirectStatusAssignmentChecker"""

    name = "colrev-direct-status-assign"

    msgs = {
        "W0931": (
            "Direct status assignment",
            "colrev-direct-status-assign",
            "Emitted when a colrev-status is directly assigned "
            + "(instead of using record.set_stautus)",
        ),
    }

    @only_required_for_messages("colrev-direct-status-assign")
    def visit_assign(self, node: nodes.Assign) -> None:
        """
        Detect direct assignment of colrev_status.
        """

        if len(node.targets) != 1:
            return

        if not hasattr(node.targets[0], "slice"):
            return

        if hasattr(node.targets[0].slice, "value"):
            if Fields.STATUS == node.targets[0].slice.value:
                self.add_message(self.name, node=node)  # , confidence=HIGH)
            return

        if hasattr(node.targets[0].slice, "attrname"):
            if "STATUS" == node.targets[0].slice.attrname:
                # Note : may also check whether it is Fields.STATUS.
                self.add_message(self.name, node=node)  # , confidence=HIGH)


def register(linter: PyLinter) -> None:
    """required method to auto register this checker"""

    linter.register_checker(DirectStatusAssignmentChecker(linter))
