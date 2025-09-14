#! /usr/bin/env python
"""Scipt to screen for deduplication errors."""
from __future__ import annotations

import typing

import pandas as pd

import colrev.ops.dedupe
from colrev.constants import Fields


def load_dedupe_false_positives(*, dedupe_operation: colrev.ops.dedupe.Dedupe) -> list:
    """Load the dedupe false positives marked in the Excel or txt file"""
    false_positives = []
    if dedupe_operation.dupe_file.is_file():
        dupes = pd.read_excel(dedupe_operation.dupe_file)
        dupes.fillna("", inplace=True)
        c_to_correct = dupes.loc[dupes["error"] != "", "cluster_id"].to_list()
        dupes = dupes[dupes["cluster_id"].isin(c_to_correct)]
        false_positives = (
            dupes.groupby(["cluster_id"], group_keys=False)[Fields.ID]
            .apply(list)
            .tolist()
        )
    return false_positives


def load_dedupe_false_negatives(*, dedupe_operation: colrev.ops.dedupe.Dedupe) -> list:
    """Load the dedupe false negatives marked in the Excel file"""

    false_negatives: typing.List[dict] = []
    if (
        dedupe_operation.non_dupe_file_xlsx.is_file()
        or dedupe_operation.non_dupe_file_txt.is_file()
    ):
        ids_to_merge = []
        if dedupe_operation.non_dupe_file_xlsx.is_file():
            non_dupes = pd.read_excel(dedupe_operation.non_dupe_file_xlsx)
            non_dupes.fillna("", inplace=True)
            c_to_correct = non_dupes.loc[
                non_dupes["error"] != "", "cluster_id"
            ].to_list()
            non_dupes = non_dupes[non_dupes["cluster_id"].isin(c_to_correct)]
            ids_to_merge = (
                non_dupes.groupby(["cluster_id"], group_keys=False)[Fields.ID]
                .apply(list)
                .tolist()
            )
        if dedupe_operation.non_dupe_file_txt.is_file():
            content = dedupe_operation.non_dupe_file_txt.read_text()
            ids_to_merge = [x.split(",") for x in content.splitlines()]
            for id_1, id_2 in ids_to_merge:
                print(f"{id_1} - {id_2}")

        false_negatives = []
        for id_list in ids_to_merge:
            if 2 == len(id_list):
                false_negatives.append(
                    {
                        "ID1": id_list[0],
                        "ID2": id_list[1],
                        "decision": "duplicate",
                    }
                )
            else:
                for i, idc in enumerate(id_list):
                    if 0 == i:
                        continue
                    false_negatives.append(
                        {
                            "ID1": id_list[0],
                            "ID2": idc,
                            "decision": "duplicate",
                        }
                    )
    return false_negatives
