#!/usr/bin/env python3
"""Scripts for the load process."""
from __future__ import annotations

import typing
from pathlib import Path

import colrev.record
import colrev.ui_cli.cli_colors as colors


def __select_source(
    *,
    source_candidates: list,
) -> dict:
    print(f"{colors.ORANGE}Select search source{colors.END}:")
    for i, heuristic_source in enumerate(source_candidates):
        highlight_color = ""
        if heuristic_source["confidence"] >= 0.7:
            highlight_color = colors.GREEN
        elif heuristic_source["confidence"] >= 0.5:
            highlight_color = colors.ORANGE
        print(
            f"{highlight_color}{i+1} "
            f"(confidence: {round(heuristic_source['confidence'], 2)}):"
            f" {heuristic_source['source_candidate'].endpoint}{colors.END}"
        )

    while True:
        selection = input("select nr")
        if not selection.isdigit():
            continue
        if int(selection) in range(1, len(source_candidates) + 1):
            heuristic_source = source_candidates[int(selection) - 1]
            return heuristic_source


def __select_source_from_heuristics(
    *, filename: Path, source_candidates: list
) -> colrev.settings.SearchSource:
    print(f"Search file {filename}")
    if 1 == len(source_candidates):
        heuristic_source = source_candidates[0]
    else:
        heuristic_source = __select_source(source_candidates=source_candidates)

    if "colrev.unknown_source" == heuristic_source["source_candidate"].endpoint:
        cmd = "Enter the search query (or NA)".ljust(25, " ") + ": "
        query_input = ""
        query_input = input(cmd)
        if query_input not in ["", "NA"]:
            heuristic_source["source_candidate"].search_parameters = {
                "query": query_input
            }
        else:
            heuristic_source["source_candidate"].search_parameters = {}

    print(f"Source name: {heuristic_source['source_candidate'].endpoint}")

    heuristic_source["source_candidate"].comment = None

    return heuristic_source["source_candidate"]


def select_new_source(
    *, heuristic_result_list: dict
) -> typing.List[colrev.settings.SearchSource]:
    """Select the new source from the heuristic_result_list."""

    new_sources = []
    for filename, source_candidates in heuristic_result_list.items():
        new_sources.append(
            __select_source_from_heuristics(
                filename=filename, source_candidates=source_candidates
            )
        )
    return new_sources
