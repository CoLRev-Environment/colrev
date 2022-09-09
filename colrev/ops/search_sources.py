#!/usr/bin/env python3
from __future__ import annotations

import typing

import colrev.process

# pylint: disable=too-few-public-methods


class SearchSources:
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:

        package_manager = review_manager.get_package_manager()

        self.all_available_packages_names = package_manager.discover_packages(
            script_type="SearchSource", installed_only=True
        )
        required_search_scripts = [
            r for s in review_manager.settings.sources for r in s.source_prep_scripts
        ] + [{"endpoint": k} for k in list(self.all_available_packages_names.keys())]

        self.type = colrev.process.ProcessType.check

        check_process = colrev.process.CheckProcess(review_manager=review_manager)
        package_manager = review_manager.get_package_manager()
        self.search_source_scripts: dict[
            str, typing.Any
        ] = package_manager.load_packages(
            process=check_process,
            scripts=required_search_scripts,
            script_type="SearchSource",
        )


if __name__ == "__main__":
    pass
