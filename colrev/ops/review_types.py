#!/usr/bin/env python3
"""CoLRev review types: Initial setup."""
from __future__ import annotations

import typing

import colrev.process.operation
from colrev.constants import PackageEndpointType

# pylint: disable=too-few-public-methods


class ReviewTypes:
    """ReviewTypes"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        review_type: str,
    ) -> None:
        package_manager = review_manager.get_package_manager()
        check_operation = colrev.process.operation.CheckOperation(review_manager)

        self.all_available_packages_names = package_manager.discover_packages(
            package_type=PackageEndpointType.review_type,
            installed_only=True,
        )

        packages_to_load = [{"endpoint": review_type}]

        self.packages: dict[str, typing.Any] = package_manager.load_packages(
            package_type=PackageEndpointType.review_type,
            selected_packages=packages_to_load,
            operation=check_operation,
            ignore_not_available=False,
        )
