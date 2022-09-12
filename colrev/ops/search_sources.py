#!/usr/bin/env python3
from __future__ import annotations

import typing
from dataclasses import asdict
from pathlib import Path

import colrev.process

# pylint: disable=too-few-public-methods


class SearchSources:
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:

        package_manager = review_manager.get_package_manager()
        check_process = colrev.process.CheckProcess(review_manager=review_manager)

        self.all_available_packages_names = package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageType.search_source,
            installed_only=True,
        )
        self.all_available_packages = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageType.search_source,
            selected_packages=[
                {
                    "endpoint": k,
                    "filename": Path(""),
                    "search_type": colrev.settings.SearchType.DB,
                    "source_name": k,
                    "source_identifier": f"{k}",
                    "search_parameters": "",
                    "load_conversion_script": {},
                }
                for k in list(self.all_available_packages_names.keys())
            ],
            process=check_process,
        )

        self.packages: dict[str, typing.Any] = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageType.search_source,
            selected_packages=[asdict(s) for s in review_manager.settings.sources],
            process=check_process,
            ignore_not_available=True,
        )


if __name__ == "__main__":
    pass
