#!/usr/bin/env python3
"""Linter for CoLRev - SearchSource packages importing requests.

Network I/O should be extracted to a dedicated :mod:`api` module.
"""
from __future__ import annotations

import typing

from astroid import nodes
from pylint import checkers
from pylint.checkers.utils import only_required_for_messages

if typing.TYPE_CHECKING:  # pragma: no cover
    from pylint.lint import PyLinter


class SearchSourceRequestsImportChecker(checkers.BaseChecker):
    """SearchSourceRequestsImportChecker"""

    name = "colrev-search-source-requests-import"

    msgs = {
        "W0933": (
            "SearchSource package imports requests. "
            + "Move requests usage to a separate api.py module.",
            "colrev-search-source-requests-import",
            "Emitted when a module containing a SearchSourcePackageBaseClass imports requests. "
            "Network I/O must live in <package>/api.py.",
        ),
    }

    @only_required_for_messages("colrev-search-source-requests-import")
    def visit_module(self, node: nodes.Module) -> None:
        """Detect requests imports in SearchSource packages."""

        if not any(
            self._is_search_source_class(classdef)
            for classdef in node.nodes_of_class(nodes.ClassDef)
        ):
            return

        for imp in node.nodes_of_class(nodes.Import):
            if any(name == "requests" for name, _ in imp.names):
                self.add_message(self.name, node=imp)

        for impfrom in node.nodes_of_class(nodes.ImportFrom):
            if impfrom.modname == "requests":
                self.add_message(self.name, node=impfrom)

    def _is_search_source_class(self, classdef: nodes.ClassDef) -> bool:
        """Check whether class inherits from SearchSourcePackageBaseClass."""

        for base in classdef.bases:
            if (
                isinstance(base, nodes.Attribute)
                and base.attrname == "SearchSourcePackageBaseClass"
            ):
                return True
            if (
                isinstance(base, nodes.Name)
                and base.name == "SearchSourcePackageBaseClass"
            ):
                return True
        return False


def register(linter: PyLinter) -> None:  # pragma: no cover
    """Required method to auto register this checker."""

    linter.register_checker(SearchSourceRequestsImportChecker(linter))
