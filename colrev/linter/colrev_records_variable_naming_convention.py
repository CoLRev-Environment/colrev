#!/usr/bin/env python3
"""Linter for CoLRev – records/record naming and (light) type conventions"""
from __future__ import annotations

import typing

from astroid import InferenceError
from astroid import nodes
from astroid.util import Uninferable
from pylint import checkers
from pylint.checkers.utils import only_required_for_messages

if typing.TYPE_CHECKING:  # pragma: no cover
    from pylint.lint import PyLinter

# pylint: disable=broad-exception-caught


class RecordsVariableNamingConventionChecker(checkers.BaseChecker):
    """RecordsVariableNamingConvention + simple type rules"""

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

    # pylint: disable=too-many-branches
    @only_required_for_messages(
        "colrev-records-variable-naming-convention",
        "colrev-record-cannot-be-dict",
        "colrev-records-must-be-dict",
    )
    def visit_assign(self, node: nodes.Assign) -> None:
        """Check variable naming and simple type rules for 'record' and 'records'."""

        if len(node.targets) != 1:  # pragma: no cover
            return

        target = node.targets[0]
        if not hasattr(target, "name"):
            return

        assigned = node.value

        # --- 1) ORIGINAL NAMING RULE FOR load_records_dict ---
        if (
            hasattr(assigned, "func")
            and isinstance(assigned.func, nodes.Attribute)
            and assigned.func.attrname == "load_records_dict"
        ):
            expected_name = "records"
            if hasattr(assigned, "keywords"):
                for keyword in assigned.keywords:
                    if keyword.arg == "header_only":
                        if getattr(keyword.value, "value", None) is True:
                            expected_name = "records_headers"
                        else:
                            expected_name = "records"
                        break

            if target.name != expected_name:
                # Use the symbolic message id
                self.add_message("colrev-records-variable-naming-convention", node=node)

        # --- 2) SIMPLE TYPE RULES FOR 'record' and 'records' ---
        try:
            inferred = list(assigned.infer())
        except (InferenceError, StopIteration):  # pragma: no cover
            inferred = []

        # Filter out astroid's Uninferable sentinel and ignore if nothing remains.
        inferred = [n for n in inferred if n is not Uninferable]
        if not inferred:
            return

        def _is_dict(n: nodes.NodeNG) -> bool:
            if isinstance(n, nodes.Dict):
                return True
            try:
                if getattr(n, "pytype", None) and n.pytype() == "builtins.dict":
                    return True
            except Exception:  # pragma: no cover
                pass
            try:
                if getattr(n, "qname", None) and n.qname() == "builtins.dict":
                    return True
            except Exception:  # pragma: no cover
                pass
            return False

        def _type_str(n: nodes.NodeNG) -> str:
            try:
                if getattr(n, "pytype", None):
                    return n.pytype()
            except Exception:  # pragma: no cover
                pass
            try:
                if getattr(n, "qname", None):
                    return n.qname()
            except Exception:  # pragma: no cover
                pass
            return n.__class__.__name__

        any_dict = any(_is_dict(n) for n in inferred)

        # Helper: is this a call to load_records_dict?
        def _is_call_to_load_records_dict(n: nodes.NodeNG) -> bool:
            return (
                isinstance(n, nodes.Call)
                and isinstance(n.func, nodes.Attribute)
                and n.func.attrname == "load_records_dict"
            )

        # BEFORE running inference, treat direct calls to load_records_dict as dict.
        if target.name == "records" and _is_call_to_load_records_dict(assigned):
            return

        if target.name == "record" and any_dict:
            dict_node = next((n for n in inferred if _is_dict(n)), None)
            self.add_message(
                "colrev-record-cannot-be-dict",
                node=node,
                args=(_type_str(dict_node) if dict_node else "builtins.dict",),
            )

        if target.name == "records" and not any_dict:
            rep = next(iter(inferred), None)
            if rep is None:
                return
            rep_str = _type_str(rep)
            # Ignore unknown or Uninferable-like representations
            if rep_str not in ("unknown", "Uninferable", "astroid.util.Uninferable"):
                self.add_message(
                    "colrev-records-must-be-dict",
                    node=node,
                    args=(rep_str,),
                )


def register(linter: PyLinter) -> None:  # pragma: no cover
    """Required method to auto register this checker."""
    linter.register_checker(RecordsVariableNamingConventionChecker(linter))
