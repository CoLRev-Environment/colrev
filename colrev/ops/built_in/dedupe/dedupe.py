#! /usr/bin/env python
"""Default deduplication module for CoLRev"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from rapidfuzz import fuzz

import colrev.env.package_manager
import colrev.ops.built_in.dedupe.utils
import colrev.record
from colrev.constants import Fields

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

    def block_pairs_for_deduplication(self, records_df: pd.DataFrame) -> pd.DataFrame:
        """
        This method is used to block pairs for deduplication.

        Parameters:
        records_df (pd.DataFrame): The dataframe containing the records to be deduplicated.

        Returns:
        pd.DataFrame: The dataframe containing the blocked pairs for deduplication.
        """

        pairs_df = pd.DataFrame(columns=["ID1", "ID2"])

        # container_title instead of journal
        block_fields_list = [
            # TODO : remove redundant fields
            # Redundant with [Fields.AUTHOR, Fields.YEAR]:
            # [Fields.AUTHOR, Fields.YEAR, Fields.PAGES],
            [Fields.DOI],
            [Fields.URL],
            [Fields.ISBN],
            [Fields.AUTHOR, Fields.YEAR],
            [Fields.TITLE, Fields.PAGES],
            [Fields.TITLE, Fields.AUTHOR],
            [Fields.TITLE, Fields.ABSTRACT],
            [Fields.TITLE, Fields.VOLUME],
            [Fields.TITLE, Fields.CONTAINER_TITLE],
            [Fields.TITLE, Fields.YEAR],
            [Fields.YEAR, Fields.VOLUME, Fields.NUMBER],
            [Fields.YEAR, Fields.VOLUME, Fields.PAGES],
            [Fields.YEAR, Fields.NUMBER, Fields.PAGES],
            [
                Fields.CONTAINER_TITLE,
                Fields.VOLUME,
                Fields.PAGES,
            ],
            # TODO : conferences, books, ...
        ]

        for block_fields in block_fields_list:
            if not all(x in records_df.columns for x in block_fields):
                continue
            pairs = self.__create_pairs_for_block_fields(records_df, block_fields)
            pairs_df = pd.concat([pairs_df, pairs], ignore_index=True)

        pairs_df = pairs_df.drop_duplicates()

        # Obtain metadata for matching pairs
        pairs_df = pd.merge(
            pairs_df,
            records_df.add_suffix("_1"),
            left_on="ID1",
            right_on="ID_1",
            how="left",
            suffixes=("", "_1"),
        )

        pairs_df = pd.merge(
            pairs_df,
            records_df.add_suffix("_2"),
            left_on="ID2",
            right_on="ID_2",
            how="left",
            suffixes=("", "_2"),
        )

        self.__calc_similarities(pairs_df)

        return pairs_df

    def __calc_similarities(self, pairs_df: pd.DataFrame) -> pd.DataFrame:
        # Add similarities if both fields exist
        similarity_fields = [
            Fields.TITLE,
            Fields.YEAR,
            Fields.VOLUME,
            Fields.NUMBER,
            Fields.PAGES,
            Fields.ABSTRACT,
            Fields.ISBN,
            Fields.AUTHOR,
            Fields.DOI,
        ]
        for similarity_field in similarity_fields:
            # TODO : how to deal with NA?
            pairs_df[similarity_field] = pairs_df.apply(
                lambda row, sim_field=similarity_field: fuzz.token_sort_ratio(
                    str(row[f"{sim_field}_1"]), str(row[f"{sim_field}_2"])
                )
                / 100
                if row[f"{sim_field}_1"] is not None
                and row[f"{sim_field}_2"] is not None
                else 0,
                axis=1,
            )

        similarity_fields = [
            Fields.CONTAINER_TITLE,
        ]
        for similarity_field in similarity_fields:
            # TODO : how to deal with NA?
            pairs_df[similarity_field] = pairs_df.apply(
                lambda row, sim_field=similarity_field: fuzz.partial_ratio(
                    str(row[f"{sim_field}_1"]), str(row[f"{sim_field}_2"])
                )
                / 100
                if row[f"{sim_field}_1"] is not None
                and row[f"{sim_field}_2"] is not None
                else 0,
                axis=1,
            )

    def __create_pairs_for_block_fields(
        self, records_df: pd.DataFrame, block_fields: list
    ) -> pd.DataFrame:
        grouped = (
            records_df.groupby(list(block_fields), group_keys=True)["ID"]
            .apply(
                lambda x: pd.DataFrame(list(combinations(x, 2)), columns=["ID1", "ID2"])
            )
            .reset_index(drop=True)
        )
        self.review_manager.logger.info(
            f"Blocking with {block_fields}: {grouped.shape[0]} pairs"
        )
        return grouped

    # flake8: noqa: E501
    def identify_true_matches(self, pairs: pd.DataFrame) -> pd.DataFrame:
        """
        This method identifies the true matches from the given pairs.
        The pairs are compared based on various fields and their similarity scores.
        The fields used for comparison are: Pages, Volume, Title, Abstract, Author, ISBN, Container Title, Number.
        The similarity scores for these fields are calculated using the fuzz.token_sort_ratio method.
        The pairs that satisfy certain conditions based on these similarity scores are considered as true matches.

        Parameters:
        pairs (DataFrame): The DataFrame containing the pairs to be compared.

        Returns:
        DataFrame: The DataFrame containing the true matches.
        """

        # TODO : think: how do we measure similarity for missing values?

        # TODO : conditions that are redundant?
        # Queries are better for debugging (understanding which conditions do/do not apply)
        # https://jakevdp.github.io/PythonDataScienceHandbook/03.12-performance-eval-and-query.html
        # pylint: disable=line-too-long
        queries = [
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.VOLUME} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ABSTRACT} > 0.9 & {Fields.ISBN} > 0.99)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.6 & {Fields.VOLUME} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ABSTRACT} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.6 & {Fields.NUMBER} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ABSTRACT} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.VOLUME} > 0.8 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.6 & {Fields.NUMBER} > 0.8 & {Fields.ABSTRACT} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.VOLUME} > 0.8 & {Fields.NUMBER} > 0.8 & {Fields.ABSTRACT} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.VOLUME} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ABSTRACT} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.NUMBER} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ABSTRACT} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.DOI} > 0.99)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.8 & {Fields.CONTAINER_TITLE} > 0.65 & {Fields.VOLUME} > 0.85 & {Fields.ABSTRACT} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.65 & {Fields.VOLUME} > 0.85 & {Fields.ABSTRACT} > 0.8)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.75 & {Fields.VOLUME} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ABSTRACT} > 0.8)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.75 & {Fields.NUMBER} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ABSTRACT} > 0.8)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.75 & {Fields.VOLUME} > 0.8 & {Fields.NUMBER} > 0.8 & {Fields.ABSTRACT} > 0.8)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.7 & {Fields.ABSTRACT} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.ABSTRACT} > 0.9 & {Fields.ISBN} > 0.99)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.6 & {Fields.NUMBER} > 0.9 & {Fields.PAGES} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.VOLUME} > 0.9 & {Fields.NUMBER} > 0.9 & {Fields.ISBN} > 0.99)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.CONTAINER_TITLE} > 0.6 & {Fields.VOLUME} > 0.9 & {Fields.PAGES} > 0.9)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.9 & {Fields.NUMBER} > 0.9 & {Fields.PAGES} > 0.9 & {Fields.ISBN} > 0.99)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.95 & {Fields.CONTAINER_TITLE} > 0.9 & {Fields.VOLUME} > 0.8 & {Fields.PAGES} > 0.8)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.95 & {Fields.CONTAINER_TITLE} > 0.9 & {Fields.VOLUME} > 0.8 & {Fields.NUMBER} > 0.8)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.95 & {Fields.CONTAINER_TITLE} > 0.9 & {Fields.NUMBER} > 0.8 & {Fields.PAGES} > 0.8)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.95 & {Fields.VOLUME} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ISBN} > 0.99)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.95 & {Fields.VOLUME} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ISBN} > 0.99)",
            f"({Fields.AUTHOR} > 0.9 & {Fields.TITLE} > 0.95 & {Fields.VOLUME} > 0.8 & {Fields.PAGES} > 0.8 & {Fields.ISBN} > 0.99)",
            f"({Fields.AUTHOR} > 0.8 & {Fields.TITLE} > 0.99 & {Fields.CONTAINER_TITLE} > 0.99 & {Fields.DOI} > 0.99)",
            f'({Fields.ENTRYTYPE}_1 == "inproceedings" & {Fields.ENTRYTYPE}_2 == "inproceedings" & {Fields.CONTAINER_TITLE} > 0.6 & {Fields.TITLE} > 0.9 & {Fields.AUTHOR} > 0.8 & {Fields.YEAR} > 0.9)',
        ]

        if self.dedupe_operation.debug:
            if pairs.shape[0] != 0:
                self.review_manager.p_printer.pprint(pairs.iloc[0].to_dict())
                print("True merge conditions:")
                for query in queries:
                    if pairs.query(query).shape[0] > 0:
                        print(query)

        true_pairs = pairs.query("|".join(queries))

        print("TODO : continue here!")

        # TODO : the prevented-same-source merges should go into the manual list
        # Find papers with low matching dois - often indicates FALSE positive matches
        # true_pairs_mismatch_doi = true_pairs[
        #     (~pd.isna(true_pairs[Fields.DOI])) & (true_pairs[Fields.DOI] > 0) & (true_pairs[Fields.DOI] <= 0.99) &
        #     ~((true_pairs[Fields.TITLE] > 0.9) & (true_pairs[Fields.ABSTRACT] > 0.9) & ((true_pairs[Fields.CONTAINER_TITLE] > 0.9) | (true_pairs[Fields.ISBN] > 0.9)))
        # ]

        # Remove papers with low matching dois from filtered matched
        # true_pairs = true_pairs[
        #     # (pd.isna(true_pairs[Fields.DOI]))
        #     # | (true_pairs[Fields.DOI] > 0.99)
        #     # | (true_pairs[Fields.DOI] == 0)
        #     # | ~(
        #     #     (true_pairs[Fields.TITLE] > 0.9)
        #     #     & (true_pairs[Fields.ABSTRACT] > 0.9)
        #     #     & (
        #     #         (true_pairs[Fields.CONTAINER_TITLE] > 0.9)
        #     #         | (true_pairs[Fields.ISBN] > 0.9)
        #     #     )
        #     # )
        # ]

        # exclude conditions
        queries = [
            f"({Fields.DOI} < 0.99 & {Fields.DOI} > 0.01)",
            f'(title_1.str.contains("editor")  & {Fields.NUMBER} < 1)',
        ]

        if self.dedupe_operation.debug:
            if pairs.shape[0] == 0:
                print("Exclude conditions:")
                for query in queries:
                    if pairs.query(query).shape[0] == 0:
                        print(query)

        true_pairs = true_pairs.query("~(" + " | ".join(queries) + ")")

        true_pairs = true_pairs.drop_duplicates()

        # # Make year numeric, then find matches where year differs
        # true_pairs['year1'] = pd.to_numeric(true_pairs['year1'], errors='coerce')
        # true_pairs['year2'] = pd.to_numeric(true_pairs['year2'], errors='coerce')
        # year_mismatch = true_pairs[true_pairs['year1'] != true_pairs['year2']]
        # year_mismatch_minor1 = year_mismatch[year_mismatch['year1'] == year_mismatch['year2'] + 1]
        # year_mismatch_minor2 = year_mismatch[year_mismatch['year1'] == year_mismatch['year2'] - 1]

        # year_mismatch_minor = pd.concat([year_mismatch_minor1, year_mismatch_minor2])
        # year_mismatch_minor = year_mismatch_minor.drop_duplicates()

        # # Identify where year differs >1 and remove from filtered dataset - need to manually deduplicate
        # year_mismatch_major = year_mismatch[~year_mismatch.index.isin(year_mismatch_minor.index)]
        # true_pairs = true_pairs[~true_pairs.index.isin(year_mismatch_major.index)]

        # true_pairs = true_pairs.drop_duplicates()

        # # Get potential duplicates for manual deduplication
        # maybe_pairs = pairs[
        #     (pairs[Fields.TITLE] > 0.85) & (pairs['author'] > 0.75) |
        #     (pairs[Fields.TITLE] > 0.8) & (pairs[Fields.ABSTRACT] > 0.8) |
        #     (pairs[Fields.TITLE] > 0.8) & (pairs[Fields.ISBN] > 0.99) |
        #     (pairs[Fields.TITLE] > 0.8) & (pairs[Fields.CONTAINER_TITLE] > 0.8) |
        #     (pd.isna(pairs[Fields.DOI]) | (pairs[Fields.DOI] > 0.99) | (pairs[Fields.DOI] == 0)) &
        #     ~((pd.to_numeric(pairs['year1'], errors='coerce') - pd.to_numeric(pairs['year2'], errors='coerce') > 1) |
        #     (pd.to_numeric(pairs['year2'], errors='coerce') - pd.to_numeric(pairs['year1'], errors='coerce') > 1))
        # ]

        # # maybe_pairs['record_ID1'] = maybe_pairs['record_ID1'].astype(str)
        # # maybe_pairs['record_ID2'] = maybe_pairs['record_ID2'].astype(str)
        # # true_pairs['record_ID1'] = true_pairs['record_ID1'].astype(str)
        # # true_pairs['record_ID2'] = true_pairs['record_ID2'].astype(str)

        # # # Get pairs required for manual dedup which are not in true pairs
        # # maybe_pairs = maybe_pairs[~maybe_pairs.set_index(['record_ID1', 'record_ID2']).index.isin(true_pairs.set_index(['record_ID1', 'record_ID2']).index)]

        # # # Add in problem doi matching pairs and different year data in ManualDedup
        # # important_mismatch = pd.concat([true_pairs_mismatch_doi, year_mismatch_major])
        # important_mismatch = true_pairs_mismatch_doi
        # maybe_pairs = pd.concat([maybe_pairs, important_mismatch])
        # maybe_pairs = maybe_pairs.drop_duplicates()

        # # true_pairs = true_pairs[['author1', 'author2', 'title1', 'title2', 'year1', 'year2', 'journal1', 'journal2', 'doi1', 'doi2', 'record_ID1', 'record_ID2']]
        maybe_pairs = pd.DataFrame()
        return {"true_pairs": true_pairs, "maybe_pairs": maybe_pairs}

    def run_dedupe(self) -> None:
        """Run default dedupe"""

        records = self.review_manager.dataset.load_records_dict()
        records_df = pd.DataFrame.from_dict(records, orient="index")

        # TODO: return df from dedupe_operation.prep_records()

        records = self.dedupe_operation.prep_records(records_df=records_df)
        records_df = pd.DataFrame.from_dict(records, orient="index")

        if self.dedupe_operation.debug:
            # TODO : the dedupe is benchmarked on the historical dataset?! -> move debug to the jupyter notebook?
            self.review_manager.verbose_mode = True
            origin1, origin2 = input("Provide ids (separated by ;)").split(";")
            records_df = records_df[
                records_df["colrev_origin"].apply(
                    lambda x: origin1 in x or origin2 in x
                )
            ]
            self.review_manager.p_printer.pprint(records_df.iloc[0].to_dict())
            self.review_manager.p_printer.pprint(records_df.iloc[1].to_dict())

        deduplication_pairs = self.block_pairs_for_deduplication(records_df)
        deduplication_pairs.to_csv("dedupe_pairs.csv")

        # TODO generate_dup_id : get connected components of the graph

        result = self.identify_true_matches(deduplication_pairs)

        result["true_pairs"]["decision"] = "duplicate"
        potential_duplicates = result["true_pairs"][["ID1", "ID2", "decision"]].to_dict(
            "records"
        )

        # potential_duplicates = []

        if self.dedupe_operation.debug:
            return

        self.dedupe_operation.apply_merges(results=potential_duplicates)

        self.review_manager.create_commit(
            msg="Merge duplicate records",
        )

        # TODO : maybes
