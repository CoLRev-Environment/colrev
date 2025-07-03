#!/usr/bin/env python3
"""Scripts for the load process."""
from __future__ import annotations

import typing
from pathlib import Path

import inquirer

from colrev.constants import Colors
from colrev.constants import EndpointType

if typing.TYPE_CHECKING:
    import colrev.settings
    import colrev.ops.search

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
        # sort choices by confidence
        choices.sort(key=lambda x: x[1]["confidence"], reverse=True)
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
    ) -> colrev.settings.SearchSource:
        if 1 == len(source_candidates):
            heuristic_source_dict = source_candidates[0]
            self.search_operation.review_manager.logger.info(
                f"Automatically selected {heuristic_source_dict['source_candidate'].endpoint}"
            )
        else:
            heuristic_source_dict = self._select_source(
                source_candidates=source_candidates
            )
            self.search_operation.review_manager.logger.info(
                f"Selected {heuristic_source_dict['source_candidate'].endpoint}"
            )

        candidate: colrev.settings.SearchSource = heuristic_source_dict[
            "source_candidate"
        ]
        search_source_class = self.package_manager.get_package_endpoint_class(
            package_type=EndpointType.search_source,
            package_identifier=candidate.endpoint,
        )
        endpoint = search_source_class(
            source_operation=self,
            settings=candidate.model_dump(),
        )

        params = f"search_file={filename}"
        source = endpoint.add_endpoint(
            operation=self.search_operation,
            params=params,
        )
        return source

    def add_new_sources(self) -> typing.List[colrev.settings.SearchSource]:
        """Select the new source from the heuristic_result_list."""

        new_search_files = self.search_operation.get_new_search_files()
        sources_added = []

        for filename in new_search_files:
            self.search_operation.review_manager.logger.info(
                f"Discover and add new DB source: {filename}"
            )
            heuristic_list = self.search_operation.get_new_source_heuristic(filename)
            for source_candidates in heuristic_list:
                source = self._select_source_from_heuristics(
                    filename=filename, source_candidates=source_candidates
                )
                sources_added.append(source)
        return sources_added
