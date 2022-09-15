#!/usr/bin/env python3
from __future__ import annotations

import typing

import colrev.process

# pylint: disable=too-few-public-methods


class ReviewTypes:
    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        review_type: str = None,
    ) -> None:

        package_manager = review_manager.get_package_manager()
        check_process = colrev.process.CheckProcess(review_manager=review_manager)

        self.all_available_packages_names = package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageType.review_type,
            installed_only=True,
        )

        packages_to_load = [{"endpoint": review_type}]
        if not review_type:
            packages_to_load = [
                {"endpoint": review_manager.settings.project.review_type}
            ]
        self.packages: dict[str, typing.Any] = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageType.review_type,
            selected_packages=packages_to_load,
            process=check_process,
            ignore_not_available=False,
        )


if __name__ == "__main__":
    pass
