#!/usr/bin/env python3
"""Linter for CoLRev - direct status assignment"""
from __future__ import annotations

import typing

from astroid import nodes
from pylint import checkers
from pylint.checkers.utils import only_required_for_messages

from colrev.constants import Fields

if typing.TYPE_CHECKING:  # pragma: no cover
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

        if len(node.targets) != 1 or not hasattr(
            node.targets[0], "slice"
        ):  # pragma: no cover
            return

        if hasattr(node.targets[0].slice, "value"):
            if Fields.STATUS == node.targets[0].slice.value:
                self.add_message(self.name, node=node)
            return

    @only_required_for_messages("colrev-direct-status-assign")
    def visit_call(self, node: nodes.Assign) -> None:
        """
        Detect direct assignment of colrev_status.
        """
        if isinstance(node.func, nodes.Attribute) and node.func.attrname == "update":
            for keyword in node.keywords:
                if keyword.arg == "colrev_status":
                    self.add_message("colrev-direct-status-assign", node=node)


def register(linter: PyLinter) -> None:  # pragma: no cover
    """Required method to auto register this checker."""

    linter.register_checker(DirectStatusAssignmentChecker(linter))
