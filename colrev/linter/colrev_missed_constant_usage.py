#!/usr/bin/env python3
"""Linter for CoLRev - missed constant usage"""
from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes
from pylint import checkers
from pylint.checkers.utils import only_required_for_messages

from colrev.constants import Fields

if TYPE_CHECKING:
    from pylint.lint import PyLinter

# Should ensure that constants are used (instead of strings)


class MissedConstantUsageChecker(checkers.BaseChecker):
    """MissedConstantUsageChecker"""

    name = "colrev-missed-constant-usage"

    msgs = {
        "W0932": (
            "Missed constant usage",
            "colrev-missed-constant-usage",
            "Emitted when a string is used instead of a constant "
            + "(in colrev/constants.py) ",
        ),
    }
    # TODO : ENTRYTYPES etc.
    constants = [getattr(Fields, v) for v in dir(Fields) if not v.startswith("__")]

    @only_required_for_messages("direct-status-assign")
    def visit_assign(self, node: nodes.Assign) -> None:
        """
        Detect missed constant usage.
        """

        if len(node.targets) != 1:
            return

        if not hasattr(node.targets[0], "slice"):
            return

        if not hasattr(node.targets[0].slice, "value"):
            return

        # TODO : check similar strings (to catch typos?)
        if node.targets[0].slice.value in self.constants:
            self.add_message(self.name, node=node)  # , confidence=HIGH)


def register(linter: PyLinter) -> None:
    """required method to auto register this checker"""

    linter.register_checker(MissedConstantUsageChecker(linter))
