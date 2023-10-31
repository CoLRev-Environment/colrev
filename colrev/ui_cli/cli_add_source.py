#!/usr/bin/env python3
"""Scripts for the load process."""
from __future__ import annotations

from pathlib import Path

import colrev.record
from colrev.constants import Colors

# pylint: disable=too-few-public-methods


class CLISourceAdder:
    """CLI utility to add SearchSources"""

    def __init__(self, *, search_operation: colrev.ops.search.Search) -> None:
        self.search_operation = search_operation
        self.review_manager = search_operation.review_manager
        self.package_manager = self.review_manager.get_package_manager()

    def __select_source(
        self,
        *,
        source_candidates: list,
    ) -> dict:
        print(f"{Colors.ORANGE}Select search source{Colors.END}:")
        for i, heuristic_source in enumerate(source_candidates):
            highlight_color = ""
            if heuristic_source["confidence"] >= 0.7:
                highlight_color = Colors.GREEN
            elif heuristic_source["confidence"] >= 0.5:
                highlight_color = Colors.ORANGE
            print(
                f"{highlight_color}{i+1} "
                f"(confidence: {round(heuristic_source['confidence'], 2)}):"
                f" {heuristic_source['source_candidate'].endpoint}{Colors.END}"
            )

        while True:
            selection = input("select nr")
            if not selection.isdigit():
                continue
            if int(selection) in range(1, len(source_candidates) + 1):
                heuristic_source = source_candidates[int(selection) - 1]
                return heuristic_source

    def __select_source_from_heuristics(
        self, *, filename: Path, source_candidates: list
    ) -> None:
        if 1 == len(source_candidates):
            heuristic_source_dict = source_candidates[0]
        else:
            heuristic_source_dict = self.__select_source(
                source_candidates=source_candidates
            )

        endpoint_dict = self.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[heuristic_source_dict["source_candidate"].get_dict()],
            operation=self.search_operation,
            only_ci_supported=self.review_manager.in_ci_environment(),
        )

        endpoint = endpoint_dict[
            heuristic_source_dict["source_candidate"].endpoint.lower()
        ]
        params = {"search_file": filename}
        source = endpoint.add_endpoint(  # type: ignore
            operation=self.search_operation,
            params=params,
        )
        self.search_operation.review_manager.settings.sources.append(source)
        self.review_manager.save_settings()
        self.review_manager.dataset.add_changes(path=filename)

    def add_new_sources(self) -> None:
        """Select the new source from the heuristic_result_list."""

        heuristic_list = self.search_operation.get_new_sources_heuristic_list()
        for filename, source_candidates in heuristic_list.items():
            self.__select_source_from_heuristics(
                filename=filename, source_candidates=source_candidates
            )
        self.search_operation.review_manager.save_settings()
