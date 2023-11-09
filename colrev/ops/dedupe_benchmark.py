#! /usr/bin/env python
"""Utility to export and evaluate dedupe benchmarks."""
from __future__ import annotations

import os
from itertools import combinations

import pandas as pd
from tqdm import tqdm

import colrev.review_manager
from colrev.constants import Fields


class DedupeBenchmarker(colrev.operation.Operation):
    """Dedupe benchmarker"""

    true_merged_origins: list
    records_df: pd.DataFrame

    def __init__(
        self,
        *,
        path: str = "",
        regenerate_benchmark_from_history: bool = False,
    ) -> None:
        if path == "":
            path = os.getcwd()

        self.review_manager = colrev.review_manager.ReviewManager(
            path_str=path, force_mode=True
        )
        self.dedupe_operation = self.review_manager.get_dedupe_operation()

        super().__init__(
            review_manager=self.review_manager,
            operations_type=colrev.operation.OperationsType.dedupe,
            notify_state_transition_operation=False,
        )

        if regenerate_benchmark_from_history:
            ret = self.get_dedupe_benchmark()
            ret["records_prepared"].to_csv("records_pre_merged.csv", index=False)
            ret["merged_origins"].to_csv("merged_record_origins.csv", index=False)
        else:
            self.__load_data()

    def __load_data(self) -> None:
        true_merged_origins_df = pd.read_csv("merged_record_origins.csv")
        self.true_merged_origins = (
            true_merged_origins_df["merged_origins"].apply(eval).tolist()
        )

        records_df = pd.read_csv("records_pre_merged.csv")
        records_df["colrev_origin"] = records_df["colrev_origin"].apply(eval).tolist()
        self.records_df = records_df

    def get_prepared_records_df(self) -> pd.DataFrame:
        prepared_records = self.dedupe_operation.prep_records(
            records_df=self.records_df
        )
        prepared_records_df = pd.DataFrame.from_dict(prepared_records, orient="index")
        return prepared_records_df

    def get_dedupe_benchmark(self) -> dict:
        """Get benchmark for dedupe"""

        def merged(record: dict) -> bool:
            return (
                len([o for o in record[Fields.ORIGIN] if not o.startswith("md_")]) != 1
            )

        records = self.review_manager.dataset.load_records_dict()

        # Select md-processed records (discard recently added/non-deduped ones)
        records = {
            r["ID"]: r
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

        # TODO: work with lists to avoid ID conflicts?!
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
        records_df = pd.DataFrame.from_dict(records, orient="index")

        merged_record_origins = []
        for row in list(records_df.to_dict(orient="records")):
            if len(row[Fields.ORIGIN]) > 1:
                merged_record_origins.append(row[Fields.ORIGIN])

        merged_record_origins = self.dedupe_operation.connected_components(
            merged_record_origins
        )
        merged_record_origins_df = pd.DataFrame(
            {"merged_origins": merged_record_origins}
        )

        return {
            "records_prepared": records_pre_merged_df,
            "records_deduped": records_df,
            "merged_origins": merged_record_origins_df,
        }

    def compare(
        self,
        *,
        predicted: list,
        blocked_df: pd.DataFrame,
    ) -> dict:
        """Compare the predicted matches and blocked pairs to the ground truth."""

        ground_truth_pairs = set()
        for item in self.true_merged_origins:
            for combination in combinations(item, 2):
                ground_truth_pairs.add("-".join(sorted(combination)))

        blocked = blocked_df.apply(
            lambda row: [row["colrev_origin_1"], row["colrev_origin_2"]], axis=1
        )
        blocked_pairs = set()
        for item in blocked:
            for combination in combinations(item, 2):
                blocked_pairs.add("-".join(sorted(combination)))

        predicted_pairs = set()
        for item in predicted:
            for combination in combinations(item, 2):
                predicted_pairs.add("-".join(sorted(combination)))

        blocks = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
        blocks_fn_list = []
        matches = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
        matches_fp_list = []
        matches_fn_list = []

        all_origins = self.records_df["colrev_origin"].tolist()
        for combination in combinations(all_origins, 2):
            pair = "-".join(sorted(combination))

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
            "blocks": blocks,
            "matches": matches,
            "blocks_FN_list": blocks_fn_list,
            "matches_FP_list": matches_fp_list,
            "matches_FN_list": matches_fn_list,
        }

    def get_cases(self, *, origin_pairs: list) -> pd.DataFrame:
        """Get the cases for origin_pairs

        records_df = [ID, origin, title, author, ...]
        origin_pairs = [(origin_1, origin_2), ...]
        """

        cases_df = pd.DataFrame()
        for pair in origin_pairs:
            pair_df = self.records_df[self.records_df["colrev_origin"].isin(pair)]
            pair_df["pair"] = ";".join(pair)
            cases_df = pd.concat([cases_df, pair_df])
        return cases_df
