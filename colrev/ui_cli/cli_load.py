#!/usr/bin/env python3
"""Scripts for the load process."""
from __future__ import annotations

import typing

import colrev.record
import colrev.ui_cli.cli_colors as colors


def __select_source(*, heuristic_result_list: list, skip_query: bool) -> dict:
    if not skip_query:
        print(f"{colors.ORANGE}Select search source{colors.END}:")
        for i, heuristic_source in enumerate(heuristic_result_list):
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
        if skip_query:
            # Use the last / unknown_source
            max_conf = 0.0
            best_candidate_pos = 0
            for i, heuristic_candidate in enumerate(heuristic_result_list):
                if heuristic_candidate["confidence"] > max_conf:
                    best_candidate_pos = i + 1
                    max_conf = heuristic_candidate["confidence"]
            if not any(c["confidence"] > 0.1 for c in heuristic_result_list):
                return [
                    x
                    for x in heuristic_result_list
                    if x["source_candidate"].endpoint == "colrev.unknown_source"
                ][0]
            selection = str(best_candidate_pos)
        else:
            selection = input("select nr")
        if not selection.isdigit():
            continue
        if int(selection) in range(1, len(heuristic_result_list) + 1):
            heuristic_source = heuristic_result_list[int(selection) - 1]
            return heuristic_source


def __heuristics_check(
    *, heuristic_result_list: list, skip_query: bool
) -> colrev.settings.SearchSource:
    if 1 == len(heuristic_result_list):
        heuristic_source = heuristic_result_list[0]
    else:
        heuristic_source = __select_source(
            heuristic_result_list=heuristic_result_list, skip_query=skip_query
        )

    if "colrev.unknown_source" == heuristic_source["source_candidate"].endpoint:
        cmd = "Enter the search query (or NA)".ljust(25, " ") + ": "
        query_input = ""
        if not skip_query:
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
    *, heuristic_result_list: list, skip_query: bool
) -> typing.List[colrev.settings.SearchSource]:
    """Select the new source from the heuristic_result_list."""
    # TODO : integrate skip_query into load.get_new_sources_heuristic_list()
    # as auto_select_best_fit flag

    # TODO : the heuristic_result_list should be a dict
    # {"new_filename": heuristic_result_list, ....}
    # currently, new_sources.append(new_source)  (in load.py/line 404)
    # is not part of the loop -> only one new_source is returned

    new_sources = []
    for heuristic_result in heuristic_result_list:
        new_sources.append(
            __heuristics_check(
                heuristic_result_list=heuristic_result, skip_query=skip_query
            )
        )
    return new_sources
