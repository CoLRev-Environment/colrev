#!/usr/bin/env python3
"""Manages CoLRev search sources."""
from __future__ import annotations

import typing
from dataclasses import asdict

import colrev.operation

# pylint: disable=too-few-public-methods


class SearchSources:
    """SearchSources (including academic databases, citation searches, PDF files)"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        package_manager = review_manager.get_package_manager()
        check_operation = colrev.operation.CheckOperation(review_manager=review_manager)

        self.all_available_packages_names = package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            installed_only=True,
        )
        # Note: class-objects only (instantiate_objects) for heuristics
        self.all_available_packages = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[
                {
                    "endpoint": k,
                }
                for k in list(self.all_available_packages_names.keys())
            ],
            operation=check_operation,
            instantiate_objects=False,
        )

        self.packages: dict[str, typing.Any] = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[asdict(s) for s in review_manager.settings.sources],
            operation=check_operation,
            ignore_not_available=False,
        )


if __name__ == "__main__":
    pass
