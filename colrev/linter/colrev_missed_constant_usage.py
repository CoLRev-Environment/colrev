#!/usr/bin/env python3
"""Linter for CoLRev - missed constant usage"""
from __future__ import annotations

import typing

from astroid import Const
from astroid import nodes
from pylint import checkers
from pylint.checkers.utils import only_required_for_messages

from colrev.constants import DefectCodes
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import OperationsType

if typing.TYPE_CHECKING:  # pragma: no cover
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

    constant_keys = [getattr(Fields, v) for v in dir(Fields) if not v.startswith("__")]
    constant_values = (
        [getattr(ENTRYTYPES, v) for v in dir(ENTRYTYPES) if not v.startswith("__")]
        + [getattr(FieldValues, v) for v in dir(FieldValues) if not v.startswith("__")]
        + [getattr(DefectCodes, v) for v in dir(DefectCodes) if not v.startswith("__")]
        + [
            getattr(OperationsType, v)
            for v in dir(OperationsType)
            if not v.startswith("__")
        ]
    )

    @only_required_for_messages("colrev-missed-constant-usage")
    def visit_assign(self, node: nodes.Assign) -> None:
        """
        Detect missed constant usage.
        """

        if len(node.targets) != 1:
            return

        assigned = node.value
        if isinstance(assigned, Const):
            if assigned.value in self.constant_values:
                self.add_message(self.name, node=node)  # , confidence=HIGH)

        if not hasattr(node.targets[0], "slice"):
            return

        if not hasattr(node.targets[0].slice, "value"):
            return

        if node.targets[0].slice.value in self.constant_keys:
            self.add_message(self.name, node=node)  # , confidence=HIGH)


def register(linter: PyLinter) -> None:  # pragma: no cover
    """Required method to auto register this checker."""

    linter.register_checker(MissedConstantUsageChecker(linter))
