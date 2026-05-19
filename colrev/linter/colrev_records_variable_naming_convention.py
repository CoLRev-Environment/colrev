#!/usr/bin/env python3
"""Linter for CoLRev – records/record naming and (light) type conventions."""

from __future__ import annotations

import typing

from astroid import InferenceError
from astroid import nodes
from astroid.util import Uninferable
from pylint import checkers
from pylint.checkers.utils import only_required_for_messages

if typing.TYPE_CHECKING:  # pragma: no cover
    from pylint.lint import PyLinter


import logging

LOGGER = logging.getLogger(__name__)
# pylint: disable=broad-exception-caught


class RecordsVariableNamingConventionChecker(checkers.BaseChecker):
    """RecordsVariableNamingConvention + simple type rules."""

    name = "colrev-records-variable-naming-convention"

    msgs = {
        "W0934": (
            "Records variable not named according to convention",
            "colrev-records-variable-naming-convention",
            "Emitted when the records variable is not named according to convention",
        ),
        "W0935": (
            "Variable 'record' should not be a dict, inferred type is %s",
            "colrev-record-cannot-be-dict",
            "Emitted when a variable named 'record' is inferred to be a dict.",
        ),
        "W0936": (
            "Variable 'records' should be a dict, inferred type is %s",
            "colrev-records-must-be-dict",
            "Emitted when a variable named 'records' is not inferred to be a dict.",
        ),
    }

    def _is_supported_assignment(self, node: nodes.Assign) -> bool:
        if len(node.targets) != 1:  # pragma: no cover
            return False

        return hasattr(node.targets[0], "name")

    def _get_assignment_target_name(self, node: nodes.Assign) -> str | None:
        target = node.targets[0]
        return getattr(target, "name", None)

    def _check_load_records_dict_naming(
        self, node: nodes.Assign, target_name: str, assigned: nodes.NodeNG
    ) -> None:
        if not (
            hasattr(assigned, "func")
            and isinstance(assigned.func, nodes.Attribute)
            and assigned.func.attrname == "load_records_dict"
        ):
            return

        expected_name = "records"
        if hasattr(assigned, "keywords"):
            for keyword in assigned.keywords:
                if keyword.arg == "header_only":
                    if getattr(keyword.value, "value", None) is True:
                        expected_name = "records_headers"
                    else:
                        expected_name = "records"
                    break

        if target_name != expected_name:
            self.add_message("colrev-records-variable-naming-convention", node=node)

    def _infer_assigned_nodes(self, assigned: nodes.NodeNG) -> list[nodes.NodeNG]:
        try:
            inferred = list(assigned.infer())
        except (InferenceError, StopIteration):  # pragma: no cover
            inferred = []

        return [n for n in inferred if n is not Uninferable]

    @staticmethod
    def _safe_pytype(n: nodes.NodeNG) -> str | None:
        pytype = getattr(n, "pytype", None)
        if not callable(pytype):
            return None

        try:
            return pytype()
        except (AttributeError, InferenceError, TypeError):
            LOGGER.debug(
                "Could not infer pytype for astroid node %s",
                n.__class__.__name__,
                exc_info=True,
            )
            return None

    @staticmethod
    def _safe_qname(n: nodes.NodeNG) -> str | None:
        qname = getattr(n, "qname", None)
        if not callable(qname):
            return None

        try:
            return qname()
        except (AttributeError, InferenceError, TypeError):
            LOGGER.debug(
                "Could not infer qname for astroid node %s",
                n.__class__.__name__,
                exc_info=True,
            )
            return None

    def _is_dict(self, n: nodes.NodeNG) -> bool:
        if isinstance(n, nodes.Dict):
            return True

        return (
            self._safe_pytype(n) == "builtins.dict"
            or self._safe_qname(n) == "builtins.dict"
        )

    def _type_str(self, n: nodes.NodeNG) -> str:
        return self._safe_pytype(n) or self._safe_qname(n) or n.__class__.__name__

    @staticmethod
    def _is_call_to_load_records_dict(n: nodes.NodeNG) -> bool:
        return (
            isinstance(n, nodes.Call)
            and isinstance(n.func, nodes.Attribute)
            and n.func.attrname == "load_records_dict"
        )

    def _check_record_assignment(
        self, node: nodes.Assign, inferred: list[nodes.NodeNG]
    ) -> None:
        any_dict = any(self._is_dict(n) for n in inferred)
        if any_dict:
            dict_node = next((n for n in inferred if self._is_dict(n)), None)
            self.add_message(
                "colrev-record-cannot-be-dict",
                node=node,
                args=(self._type_str(dict_node) if dict_node else "builtins.dict",),
            )

    def _check_records_assignment(
        self, node: nodes.Assign, assigned: nodes.NodeNG, inferred: list[nodes.NodeNG]
    ) -> None:
        if self._is_call_to_load_records_dict(assigned):
            return

        any_dict = any(self._is_dict(n) for n in inferred)
        if any_dict:
            return

        rep = next(iter(inferred), None)
        if rep is None:
            return
        rep_str = self._type_str(rep)
        if rep_str not in ("unknown", "Uninferable", "astroid.util.Uninferable"):
            self.add_message(
                "colrev-records-must-be-dict",
                node=node,
                args=(rep_str,),
            )

    @only_required_for_messages(
        "colrev-records-variable-naming-convention",
        "colrev-record-cannot-be-dict",
        "colrev-records-must-be-dict",
    )
    def visit_assign(self, node: nodes.Assign) -> None:
        """Check variable naming and simple type rules for 'record' and 'records'."""
        if not self._is_supported_assignment(node):
            return

        target_name = self._get_assignment_target_name(node)
        if target_name is None:
            return

        assigned = node.value
        self._check_load_records_dict_naming(node, target_name, assigned)

        inferred = self._infer_assigned_nodes(assigned)
        if not inferred:
            return

        if target_name == "record":
            self._check_record_assignment(node, inferred)
        elif target_name == "records":
            self._check_records_assignment(node, assigned, inferred)


def register(linter: PyLinter) -> None:  # pragma: no cover
    """Required method to auto register this checker."""
    linter.register_checker(RecordsVariableNamingConventionChecker(linter))
