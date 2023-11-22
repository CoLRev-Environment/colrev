#! /usr/bin/env python
"""Utility to export and evaluate dedupe benchmarks."""
from __future__ import annotations

import datetime
import typing
from itertools import combinations
from pathlib import Path
from typing import Optional

import pandas as pd
from tqdm import tqdm

import colrev.ops.dedupe
import colrev.review_manager
from colrev.constants import Fields


class DedupeBenchmarker:
    """Dedupe benchmarker"""

    # pylint: disable=too-many-instance-attributes

    true_merged_origins: list
    records_df: pd.DataFrame

    def __init__(
        self,
        *,
        benchmark_path: Optional[Path] = None,
        regenerate_benchmark_from_history: bool = False,
        colrev_project_path: Optional[Path] = None,
    ) -> None:
        if benchmark_path is None:
            benchmark_path = Path.cwd()
        self.benchmark_path = Path(benchmark_path).resolve()
        if colrev_project_path is None:
            self.colrev_project_path = benchmark_path
        else:
            self.colrev_project_path = colrev_project_path

        self.records_pre_merged_path = Path(
            self.benchmark_path, "records_pre_merged.csv"
        )
        self.merged_record_origins_path = Path(
            self.benchmark_path, "merged_record_origins.csv"
        )
        if regenerate_benchmark_from_history:
            self.__get_dedupe_benchmark()
        else:
            self.__load_data()

    def __load_data(self) -> None:
        true_merged_origins_df = pd.read_csv(str(self.merged_record_origins_path))
        self.true_merged_origins = (
            true_merged_origins_df["merged_origins"].apply(eval).tolist()
        )

        records_df = pd.read_csv(str(self.records_pre_merged_path))
        records_df[Fields.ORIGIN] = records_df[Fields.ORIGIN].apply(eval).tolist()
        self.records_df = records_df

    def get_records_for_dedupe(self) -> pd.DataFrame:
        """
        Get (pre-processed) records for dedupe

        Returns:
            pd.DataFrame: Pre-processed records for dedupe
        """

        prepared_records_df = colrev.ops.dedupe.Dedupe.get_records_for_dedupe(
            records_df=self.records_df
        )
        return prepared_records_df

    # pylint: disable=too-many-locals
    def __get_dedupe_benchmark(self) -> None:
        """Get benchmark for dedupe"""

        def merged(record: dict) -> bool:
            return (
                len([o for o in record[Fields.ORIGIN] if not o.startswith("md_")]) != 1
            )

        self.review_manager = colrev.review_manager.ReviewManager(
            path_str=str(self.colrev_project_path), force_mode=True
        )
        self.dedupe_operation = self.review_manager.get_dedupe_operation()

        records = self.review_manager.dataset.load_records_dict()
        for record in records.values():
            if Fields.STATUS not in record:
                record[Fields.STATUS] = colrev.record.RecordState.md_processed
                print("setting missing status")

        # Select md-processed records (discard recently added/non-deduped ones)
        records = {
            r[Fields.ID]: r
            for r in records.values()
            if r[Fields.STATUS]
            in colrev.record.RecordState.get_post_x_states(
                state=colrev.record.RecordState.md_processed
            )
        }
        # Drop origins starting with md_... (not relevant for dedupe)
        for record_dict in records.values():
            record_dict[Fields.ORIGIN] = [
                o for o in record_dict[Fields.ORIGIN] if not o.startswith("md_")
            ]

        records_pre_merged_list = [r for r in records.values() if not merged(r)]
        records_merged_origins = [
            o
            for r in records.values()
            if merged(r)
            for o in r[Fields.ORIGIN]
            if not o.startswith("md_")
        ]

        nr_commits = self.review_manager.dataset.get_repo().git.rev_list(
            "--count", "HEAD"
        )
        for hist_recs in tqdm(
            self.review_manager.dataset.load_records_from_history(),
            total=int(nr_commits),
        ):
            if len(records_merged_origins) == 0:
                break

            try:
                for hist_record_dict in hist_recs.values():
                    if any(
                        o in hist_record_dict[Fields.ORIGIN]
                        for o in records_merged_origins
                    ) and not merged(hist_record_dict):
                        # only consider post-md_prepared (non-merged) records
                        if hist_record_dict[
                            Fields.STATUS
                        ] in colrev.record.RecordState.get_post_x_states(
                            state=colrev.record.RecordState.md_prepared
                        ):
                            hist_record_dict[Fields.ORIGIN] = [
                                o
                                for o in hist_record_dict[Fields.ORIGIN]
                                if not o.startswith("md_")
                            ]
                            records_pre_merged_list.append(hist_record_dict)
                            records_merged_origins.remove(
                                [
                                    o
                                    for o in hist_record_dict[Fields.ORIGIN]
                                    if not o.startswith("md_")
                                ][0]
                            )

            except KeyError:
                break

        records_pre_merged = {r["ID"]: r for r in records_pre_merged_list}

        # drop missing from records
        # (can only evaluate record/origins that are available in records_pre_merged)
        pre_merged_orgs = {
            o for r in records_pre_merged.values() for o in r[Fields.ORIGIN]
        }
        for record_dict in records.values():
            record_dict[Fields.ORIGIN] = [
                o
                for o in record_dict[Fields.ORIGIN]
                if o in pre_merged_orgs and o not in records_merged_origins
            ]
        records = {r["ID"]: r for r in records.values() if len(r[Fields.ORIGIN]) > 0}

        assert {o for x in records_pre_merged.values() for o in x[Fields.ORIGIN]} == {
            o for x in records.values() for o in x[Fields.ORIGIN]
        }
        # [x for x in o_rec if x not in o_pre]

        records_pre_merged_df = pd.DataFrame.from_dict(
            records_pre_merged, orient="index"
        )
        self.records_pre_merged_df = records_pre_merged_df

        records_df = pd.DataFrame.from_dict(records, orient="index")
        self.records_df = records_df

        merged_record_origins = []
        for row in list(records_df.to_dict(orient="records")):
            if len(row[Fields.ORIGIN]) > 1:
                merged_record_origins.append(row[Fields.ORIGIN])

        merged_record_origins = self.dedupe_operation.connected_components(
            merged_record_origins
        )
        self.true_merged_origins = merged_record_origins
        merged_record_origins_df = pd.DataFrame(
            {"merged_origins": merged_record_origins}
        )
        records_pre_merged_df.to_csv(str(self.records_pre_merged_path), index=False)
        merged_record_origins_df.to_csv(
            str(self.merged_record_origins_path), index=False
        )

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    def compare(
        self,
        *,
        blocked_df: pd.DataFrame,
        predicted: list,
        updated_paper_pairs: list,
    ) -> dict:
        """Compare the predicted matches and blocked pairs to the ground truth."""

        ground_truth_pairs = set()
        for item in self.true_merged_origins:
            for combination in combinations(item, 2):
                ground_truth_pairs.add(";".join(sorted(combination)))

        blocked = blocked_df.apply(
            lambda row: [row["colrev_origin_1"], row["colrev_origin_2"]], axis=1
        )
        blocked_pairs = set()
        for item in blocked:
            for combination in combinations(item, 2):
                blocked_pairs.add(";".join(sorted(combination)))

        predicted_pairs = set()
        for item in predicted:
            for combination in combinations(item, 2):
                predicted_pairs.add(";".join(sorted(combination)))

        blocks = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
        blocks_fn_list = []
        matches = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
        matches_fp_list = []
        matches_fn_list = []

        all_origins = [
            origin
            for sublist in self.records_df[Fields.ORIGIN].tolist()
            for origin in sublist
        ]
        for combination in combinations(all_origins, 2):
            pair = ";".join(sorted(combination))

            if pair in blocked_pairs:
                if pair in ground_truth_pairs:
                    blocks["TP"] += 1
                else:
                    blocks["FP"] += 1
                    # Don't need a list here.
            else:
                if pair in ground_truth_pairs:
                    blocks["FN"] += 1
                    blocks_fn_list.append(combination)
                else:
                    blocks["TN"] += 1

            if pair in predicted_pairs:
                if pair in ground_truth_pairs:
                    matches["TP"] += 1
                else:
                    matches["FP"] += 1
                    matches_fp_list.append(combination)
            else:
                if pair in ground_truth_pairs:
                    matches["FN"] += 1
                    matches_fn_list.append(combination)
                else:
                    matches["TN"] += 1

        return {
            "matches": matches,
            "blocks_FN_list": blocks_fn_list,
            "matches_FP_list": matches_fp_list,
            "matches_FN_list": matches_fn_list,
            "blocks": blocks,
            "updated_paper_pairs": updated_paper_pairs,
        }

    def export_cases(
        self, *, prepared_records_df: pd.DataFrame, results: dict
    ) -> pd.DataFrame:
        """Get the cases for results

        records_df = [ID, origin, title, author, ...]
        results = {"blocks_FN_list", "matches_FP_list", "matches_FN_list", "updated_paper_pairs"}
        """

        for list_name in [
            "blocks_FN_list",
            "matches_FP_list",
            "matches_FN_list",
            "updated_paper_pairs",
        ]:
            origin_pairs = results[list_name]
            cases_df = pd.DataFrame()
            for pair in origin_pairs:
                pair_df = prepared_records_df[
                    prepared_records_df[Fields.ORIGIN].isin(pair)
                ].copy()
                pair_df.loc[:, "case"] = ";".join(pair)
                cases_df = pd.concat([cases_df, pair_df])

            if not cases_df.empty:
                cases_df = cases_df[
                    ["case", "ID", "colrev_origin"]
                    + [
                        col
                        for col in cases_df.columns
                        if col not in ["case", "ID", "colrev_origin"]
                    ]
                ]
                cases_df = cases_df.sort_values(by=["case", "ID"])

            cases_df.to_csv(self.benchmark_path / f"{list_name}.csv", index=False)

        return cases_df

    def get_runtime(self, timestamp: datetime.datetime) -> str:
        """
        Calculate the runtime.

        Args:
            timestamp (datetime.datetime): The timestamp when the deduplication was started.

        Returns:
            str: The runtime in the format "hours:minutes:seconds".
        """
        start_time = datetime.datetime.now()
        time_diff = start_time - timestamp
        runtime_in_minutes = time_diff.total_seconds() / 60

        runtime_in_hours = runtime_in_minutes / 60
        hours = int(runtime_in_hours)
        minutes = (runtime_in_hours * 60) % 60
        seconds = (runtime_in_hours * 3600) % 60
        runtime_string = f"{hours}:{int(minutes):02d}:{int(seconds):02d}"
        print(f"Runtime: {runtime_string}")
        return runtime_string

    def compare_dedupe_id(
        self,
        *,
        records_df: pd.DataFrame,
        merged_df: pd.DataFrame,
        timestamp: datetime.datetime,
    ) -> pd.DataFrame:
        """
        Compare dedupe IDs and calculate evaluation metrics.

        Args:
            records_df (pd.DataFrame): DataFrame containing the original records.
            merged_df (pd.DataFrame): DataFrame containing the merged records.
            timestamp (datetime.datetime): The timestamp when the deduplication was started.

        Returns:
            pd.DataFrame: DataFrame containing the evaluation metrics.
        """

        results: typing.Dict[str, typing.Any] = {
            "TP": 0,
            "FP": 0,
            "FN": 0,
            "TN": 0,
            "runtime": self.get_runtime(timestamp),
        }

        origin_id_dict = {
            record["colrev_origin"]: record["ID"]
            for _, record in records_df[["ID", "colrev_origin"]].iterrows()
        }
        true_merged_ids = []
        for true_merged_origin_set in self.true_merged_origins:
            true_merged_id_item = []
            for origin in true_merged_origin_set:
                true_merged_id_item.append(origin_id_dict.pop(origin))
            true_merged_ids.append(true_merged_id_item)
        true_non_merged_ids = list(origin_id_dict.values())

        # Assume that IDs are not changed (merged origins are not available)
        # For each origin-set, **exactly one** must be in the merged_df

        for true_non_merged_id in true_non_merged_ids:
            if true_non_merged_id in merged_df["ID"].tolist():
                results["TN"] += 1
            else:
                results["FP"] += 1

        for true_merged_id_set in true_merged_ids:
            nr_in_merged_df = merged_df[merged_df["ID"].isin(true_merged_id_set)].shape[
                0
            ]
            # One would always be required to be a non-duplicate (true value:negative)
            # All that are removed are true positive, all that are not removed are false negatives
            if nr_in_merged_df == 0:
                results["FP"] += 1
                results["TP"] += len(true_merged_id_set) - 1
            elif nr_in_merged_df >= 1:
                results["TN"] += 1
                results["FN"] += nr_in_merged_df - 1
                results["TP"] += len(true_merged_id_set) - nr_in_merged_df

        specificity = results["TN"] / (results["TN"] + results["FP"])
        sensitivity = results["TP"] / (results["TP"] + results["FN"])

        results["false_positive_rate"] = results["FP"] / (results["FP"] + results["TN"])

        results["specificity"] = specificity
        results["sensitivity"] = sensitivity
        results["precision"] = results["TP"] / (results["TP"] + results["FP"])

        results["f1"] = (
            2
            * (results["precision"] * results["sensitivity"])
            / (results["precision"] + results["sensitivity"])
        )

        results["dataset"] = Path(self.benchmark_path).name

        return results
