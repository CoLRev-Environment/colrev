#!/usr/bin/env python3
"""Linter for CoLRev"""
from __future__ import annotations

from astroid import nodes
from pylint import checkers
from pylint import interfaces
from pylint.checkers.utils import only_required_for_messages

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from pylint.lint import PyLinter


class DirectStatusAssignmentChecker(checkers.BaseChecker):
    """DirectStatusAssignmentChecker"""

    __implements__ = interfaces.IAstroidChecker

    name = "direct-status-assign"

    msgs = {
        "W0931": (
            "Direct status assignment",
            "direct-status-assign",
            "Emitted when a colrev-status is directly assigned "
            + "(instead of using record.set_stautus)",
        ),
    }

    @only_required_for_messages("direct-status-assign")
    def visit_assign(self, node: nodes.Assign) -> None:
        """
        Detect direct assignment of colrev_status.
        """

        # if 706 != node.fromlineno:
        #   return

        # if not isinstance(node.targets[0], nodes.Dict):
        #     return
        if len(node.targets) != 1:
            return

        if not hasattr(node.targets[0], "slice"):
            return

        if not hasattr(node.targets[0].slice, "value"):
            return

        if "colrev_status" == node.targets[0].slice.value:
            # for variable, value in vars(node.targets[0].slice).items():
            #   if variable[:1] == '_':
            #       print(f"{variable}{value}")
            # print(node.targets[0].nodes_of_class)
            # print(dir(node.targets[0]))
            self.add_message("direct-status-assign", node=node)  # , confidence=HIGH)


def register(linter: PyLinter) -> None:
    """required method to auto register this checker"""

    linter.register_checker(DirectStatusAssignmentChecker(linter))
