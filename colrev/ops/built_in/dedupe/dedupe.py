#! /usr/bin/env python
"""Default deduplication module for CoLRev"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import List
from typing import TYPE_CHECKING

import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from pandas import DataFrame
from rapidfuzz import fuzz

import colrev.env.package_manager
import colrev.ops.built_in.dedupe.utils
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.dedupe

# pylint: disable=too-many-arguments
# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.DedupePackageEndpointInterface)
@dataclass
class Dedupe(JsonSchemaMixin):
    """Default deduplication"""

    ci_supported: bool = True

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
        settings: dict,
    ):
        self.settings = self.settings_class.load_settings(data=settings)
        self.dedupe_operation = dedupe_operation
        self.review_manager = dedupe_operation.review_manager

    def match_citations(self, formatted_citations: DataFrame) -> Any | None:
        def jaro_winkler_similarity(str1: str, str2: str) -> Any:
            return fuzz.jaro_winkler(str1, str2)

        # ROUND 1
        block_fields_round1 = [(2, 8), (1, 2), (2, 5), 6]
        newpairs = self.compare_dedup(formatted_citations, block_fields_round1)

        # ROUND 2
        block_fields_round2 = [(1, 3, 8), (4, 9, 8), (10, 9, 8), (2, 10)]
        newpairs2 = self.compare_dedup(formatted_citations, block_fields_round2)

        # ROUND 3
        block_fields_round3 = [(3, 8, 9), (3, 7, 9), (3, 8, 7)]
        newpairs3 = self.compare_dedup(formatted_citations, block_fields_round3)

        # ROUND 4
        block_fields_round4 = [(1, 3), (3, 2), (2, 9), (2, 4)]
        newpairs4 = self.compare_dedup(formatted_citations, block_fields_round4)

        # Combine all possible pairs
        linkedpairs = pd.concat(
            [newpairs, newpairs2, newpairs3, newpairs4]
        ).drop_duplicates()
        print(linkedpairs)

        if linkedpairs.empty:
            return None

        # Obtain metadata for matching pairs
        pairs = linkedpairs.apply(
            lambda row: self.get_metadata(
                row, formatted_citations, jaro_winkler_similarity
            ),
            axis=1,
        )

        return pairs

    def compare_dedup(
        self, formatted_citations: DataFrame, block_fields: List
    ) -> DataFrame:
        pairs = formatted_citations.apply(
            lambda row: self.compare_dedup_inner(
                row, formatted_citations, block_fields
            ),
            axis=1,
        )
        return pairs.dropna()

    def compare_dedup_inner(
        self, row: Any, formatted_citations: DataFrame, block_fields: List
    ) -> DataFrame:
        try:
            newpairs = formatted_citations.compare.dedup(
                row, blockfld=block_fields, exclude=["record_id", "source", "label"]
            )
            linkedpairs = pd.DataFrame(newpairs.pairs)
            return linkedpairs
        except Exception:
            return None

    def get_metadata(
        self, row: Any, formatted_citations: DataFrame, similarity_function: Any
    ) -> pd.Series:
        metadata_columns = [
            "author",
            "title",
            "abstract",
            "year",
            "number",
            "pages",
            "volume",
            "journal",
            "isbn",
            "doi",
        ]
        metadata = {}
        for col in metadata_columns:
            id1, id2 = row["id1"], row["id2"]
            metadata[f"{col}1"] = formatted_citations[col][id1]
            metadata[f"{col}2"] = formatted_citations[col][id2]
            metadata[col] = similarity_function(
                metadata[f"{col}1"], metadata[f"{col}2"]
            )

        return pd.Series(metadata)

    def run_dedupe(self) -> None:
        """Run default dedupe"""

        records = self.review_manager.dataset.load_records_dict()
        records_df = pd.DataFrame.from_dict(records, orient="index")
        result = self.match_citations(records_df)
        input(result)

        potential_duplicates: List = []

        # apply:
        self.dedupe_operation.apply_merges(results=potential_duplicates)

        # commit
        self.review_manager.create_commit(
            msg="Merge duplicate records",
        )
