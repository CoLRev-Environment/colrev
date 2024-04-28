#!/usr/bin/env python3
"""Scripts for the load process."""
from __future__ import annotations

from pathlib import Path

import inquirer

import colrev.record.record
from colrev.constants import Colors
from colrev.constants import EndpointType

# pylint: disable=too-few-public-methods


class CLISourceAdder:
    """CLI utility to add SearchSources"""

    def __init__(self, *, search_operation: colrev.ops.search.Search) -> None:
        self.search_operation = search_operation
        self.review_manager = search_operation.review_manager
        self.package_manager = self.review_manager.get_package_manager()

    def _select_source(
        self,
        *,
        source_candidates: list,
    ) -> dict:

        choices = [
            (
                f"{heuristic_source['source_candidate'].endpoint} "
                f"(confidence: {round(heuristic_source['confidence'], 2)}): ",
                heuristic_source,
            )
            for heuristic_source in source_candidates
        ]
        questions = [
            inquirer.List(
                "source",
                message=f"{Colors.ORANGE}Select search source{Colors.END}:",
                choices=choices,
            ),
        ]
        selected_heuristic_source = inquirer.prompt(questions)["source"]
        return selected_heuristic_source

    def _select_source_from_heuristics(
        self, *, filename: Path, source_candidates: list
    ) -> None:
        if 1 == len(source_candidates):
            heuristic_source_dict = source_candidates[0]
        else:
            heuristic_source_dict = self._select_source(
                source_candidates=source_candidates
            )

        search_source_class = self.package_manager.get_package_endpoint_class(
            package_type=EndpointType.search_source,
            package_identifier=heuristic_source_dict["source_candidate"],
        )
        endpoint = search_source_class(
            source_operation=self,
            settings=heuristic_source_dict["source_candidate"].get_dict(),
        )

        params = {"search_file": filename}
        source = endpoint.add_endpoint(  # type: ignore
            operation=self.search_operation,
            params=params,
        )
        self.search_operation.review_manager.settings.sources.append(source)
        self.review_manager.save_settings()
        self.review_manager.dataset.add_changes(filename)

    def add_new_sources(self) -> None:
        """Select the new source from the heuristic_result_list."""

        heuristic_list = self.search_operation.get_new_sources_heuristic_list()
        for filename, source_candidates in heuristic_list.items():
            self._select_source_from_heuristics(
                filename=filename, source_candidates=source_candidates
            )
        self.search_operation.review_manager.save_settings()
