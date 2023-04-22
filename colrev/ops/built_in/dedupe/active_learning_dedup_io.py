#! /usr/bin/env python
"""Deduplication based on active learning (dedupe-io)"""
from __future__ import annotations

import logging
import os
import sqlite3
import statistics
import typing
from dataclasses import dataclass
from pathlib import Path

import dedupe as dedupe_io
import pandas as pd
import psutil
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from dedupe._typing import RecordDictPair as TrainingExample
from dedupe._typing import TrainingData
from dedupe.core import unique

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.dedupe.utils
import colrev.record
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.dedupe

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-lines


@zope.interface.implementer(colrev.env.package_manager.DedupePackageEndpointInterface)
@dataclass
class ActiveLearningDedupeTraining(JsonSchemaMixin):
    """Active learning: training phase (minimum sample size of 50 required)"""

    # pylint: disable=too-many-instance-attributes

    __n_match: int
    __n_distinct: int
    __manual: bool

    settings_class = colrev.env.package_manager.DefaultSettings
    TRAINING_FILE_RELATIVE = Path(".records_dedupe_training.json")
    SETTINGS_FILE_RELATIVE = Path(".records_learned_settings")

    deduper: dedupe_io.Deduper

    ci_supported: bool = False

    # Code based on
    # https://github.com/dedupeio/dedupe-examples/blob/master/csv_example/csv_example.py

    def __init__(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,  # pylint: disable=unused-argument
        settings: dict,
    ):
        logging.basicConfig()
        logging.getLogger("dedupe.canopy_index").setLevel(logging.WARNING)

        self.settings = self.settings_class.load_settings(data=settings)
        self.training_file = (
            dedupe_operation.review_manager.path / self.TRAINING_FILE_RELATIVE
        )
        self.settings_file = (
            dedupe_operation.review_manager.path / self.SETTINGS_FILE_RELATIVE
        )

        self.local_index = dedupe_operation.review_manager.get_local_index()
        self.review_manager = dedupe_operation.review_manager

        if hasattr(dedupe_operation.review_manager, "dataset"):
            dedupe_operation.review_manager.dataset.update_gitignore(
                add=[self.SETTINGS_FILE_RELATIVE]
            )

    def setup_active_learning_dedupe(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
        retrain: bool,
        in_memory: bool,
    ) -> None:
        """Prepare data for active learning setup"""
        # pylint: disable=import-outside-toplevel
        import random

        logging.getLogger("opensearch").setLevel(logging.ERROR)
        logging.getLogger("dedupe.training").setLevel(logging.WARNING)
        logging.getLogger("dedupe.api").setLevel(logging.WARNING)

        if retrain:
            # Note : removing the training_file would be to start from scratch...
            # self.training_file.unlink(missing_ok=True)
            self.settings_file.unlink(missing_ok=True)

        dedupe_operation.review_manager.logger.info("Import data ...")

        # Possible extension: in the read_data, we may want to append the colrev_status
        # to use Gazetteer (dedupe_io) if applicable (no duplicates in pos-md_processed)

        data_d = dedupe_operation.read_data()

        # to address memory issues, we select a sample from data_d
        # and feed it to prepare_training:
        # https://github.com/dedupeio/dedupe/issues/920

        if not in_memory:
            # Note: we have to make sure that when we sample for training,
            # the not-in-memory mode is used for duplicate clustering
            # otherwise, non-sampled duplicates will not be identified
            max_training_sample_size = min(1500, len(list(data_d.keys())))
            dedupe_operation.review_manager.logger.info(
                f"Selecting a random sample of {max_training_sample_size}"
                " to avoid memory problems"
            )
            # gh_issue https://github.com/CoLRev-Environment/colrev/issues/37
            # consider similar proportions of post-md_processed/md_prepared?
            keys = random.sample(list(data_d.keys()), max_training_sample_size)
            data_d = {key: data_d[key] for key in keys}

        # dedupe_operation.review_manager.logger.debug(
        #     dedupe_operation.review_manager.p_printer.pformat(data_d)
        # )

        # def title_corpus():
        #     for record in data_d.values():
        #         yield record["title"]

        # def container_corpus():
        #     for record in data_d.values():
        #         yield record["container_title"]

        # def author_corpus():
        #     for record in data_d.values():
        #         yield record["author"]

        # Training

        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/37
        # creating a corpus from all fields may create memory issues...

        # Define the fields dedupe will pay attention to
        fields = [
            {
                "field": "author",
                "type": "String",
                # "corpus": author_corpus(),k
                "has missing": True,
                "crf": True,
            },
            {
                "field": "title",
                "type": "String",
                #  "corpus": title_corpus()
                "has missing": True,
                "crf": True,
            },
            {
                "field": "container_title",
                "variable name": "container_title",
                "type": "ShortString",
                # "corpus": container_corpus(),
                "has missing": True,
                "crf": True,
            },
            {
                "field": "year",
                "variable name": "year",
                "has missing": True,
                "type": "DateTime",
            },
            {
                "field": "volume",
                "variable name": "volume",
                "type": "ShortString",
                "has missing": True,
            },
            {
                "field": "number",
                "variable name": "number",
                "type": "ShortString",
                "has missing": True,
            },
            {
                "field": "pages",
                "type": "ShortString",
                "has missing": True,
                "crf": True,
            },
            {
                "type": "Interaction",
                "interaction variables": [
                    "container_title",
                    "year",
                    "volume",
                    "number",
                ],
            },
        ]
        # Consider using exists:
        # https://docs.dedupe.io/en/latest/Variable-definition.html#exists

        # Interactions:
        # https://docs.dedupe.io/en/latest/Variable-definition.html

        # Create a new deduper object and pass our data model to it.
        self.deduper = dedupe_io.Dedupe(fields)

        # If we have training data saved from a previous run of dedupe,
        # look for it and load it in.
        # __Note:__ if you want to train from scratch, delete the training_file

        if len(data_d) < 50:
            raise colrev_exceptions.DedupeError(
                "Sample size too small for active learning. "
                "Use simple_dedupe instead:\n"
                f"{colors.ORANGE}  colrev settings -m 'dedupe.dedupe_package_endpoints="
                f'[{{"endpoint":"colrev.simple_dedupe"}}]\'{colors.END}'
            )

        if self.training_file.is_file():
            dedupe_operation.review_manager.logger.info(
                "Reading pre-labeled training data from "
                f"{self.training_file.name} "
                "and preparing data"
            )
            dedupe_operation.review_manager.logger.info("Prepare training data")
            with open(self.training_file, "rb") as file:
                self.deduper.prepare_training(data_d, file)
        else:
            dedupe_operation.review_manager.logger.info("Prepare training data")
            # TBD: maybe use the sample_size parameter here?
            self.deduper.prepare_training(data_d)

        del data_d

        dedupe_operation.review_manager.logger.info(
            "Reading and preparation completed."
        )

    def __get_nr_duplicates(self, *, result_list: list) -> int:
        return len([i for i in result_list if "duplicate" == i["decision"]])

    def __get_nr_non_duplicates(self, *, result_list: list) -> int:
        return len([i for i in result_list if "no_duplicate" == i["decision"]])

    def apply_active_learning(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
        results: list,
    ) -> None:
        """Apply the active learning results"""
        if (
            self.__get_nr_duplicates(result_list=results) > 10
            and self.__get_nr_non_duplicates(result_list=results) > 10
        ):
            dedupe_operation.apply_merges(results=results, complete_dedupe=False)

            dedupe_operation.review_manager.logger.info("Training deduper.")

            # Using the examples we just labeled, train the deduper and learn
            # blocking predicates
            self.deduper.train(recall=0.9, index_predicates=True)
            # print(self.deduper.data_model._field_comparators)
            # print(self.deduper.predicates)

            # When finished, save our training to disk
            with open(self.training_file, "w", encoding="utf-8") as train_file:
                self.deduper.write_training(train_file)
            dedupe_operation.review_manager.dataset.add_changes(path=self.training_file)

            # Save our weights and predicates to disk.  If the settings file
            # exists, we will skip all the training and learning next time we run
            # this file.
            with open(self.settings_file, "wb") as sett_file:
                self.deduper.write_settings(sett_file)
            # self.cleanup_training()

            dedupe_operation.review_manager.create_commit(
                msg="Labeling of duplicates (active learning)",
                manual_author=True,
            )

        else:
            dedupe_operation.review_manager.logger.info(
                "Not enough duplicates/non-duplicates to train deduper."
            )
            if self.__get_nr_duplicates(result_list=results) > 0:
                print([x for x in results if "duplicate" == x["decision"]])
            if self.__get_nr_non_duplicates(result_list=results) > 30:
                if "y" == input(
                    "Set remaining records to non-duplicated "
                    "(at least 50 non-duplicates recommended) (y,n)?"
                ):
                    dedupe_operation.apply_merges(results=results, complete_dedupe=True)
                    dedupe_operation.review_manager.create_commit(
                        msg="Set remaining records to non-duplicated (not enough to train ML)",
                        manual_author=True,
                    )
                    return

        if (
            self.__get_nr_duplicates(result_list=results) == 0
            and self.__get_nr_non_duplicates(result_list=results) > 100
        ):
            if input("Set remaining records to md_processed (no duplicates)?") == "y":
                dedupe_operation.apply_merges(results=results, complete_dedupe=True)
                dedupe_operation.review_manager.create_commit(
                    msg="Set remaining records to non-duplicated",
                    manual_author=True,
                )

    def __get_record_pair_for_labeling(
        self,
        *,
        use_previous: bool,
        examples_buffer: list,
        uncertain_pairs: list[TrainingExample],
    ) -> TrainingExample:
        if use_previous:
            record_pair, _ = examples_buffer.pop(0)
        else:
            # try:
            if not uncertain_pairs:
                uncertain_pairs = self.deduper.uncertain_pairs()

            record_pair = uncertain_pairs.pop()
            # except IndexError:
            #     break
        return record_pair

    def __identical_colrev_ids(self, *, record_pair: TrainingExample) -> bool:
        # if any of the colrev_ids NA,
        # we don't know whether we have a duplicate.
        return (
            record_pair[0]["colrev_id"] == record_pair[1]["colrev_id"]
            and "NA" != record_pair[0]["colrev_id"]
            and "NA" != record_pair[1]["colrev_id"]
        )

    def __active_label_duplicate(
        self,
        *,
        manual_dedupe_decision_list: typing.List[dict],
        record_pair: TrainingExample,
        examples_buffer: list[
            tuple[TrainingExample, typing.Literal["match", "distinct", "uncertain"]]
        ],
    ) -> None:
        manual_dedupe_decision_list.append(
            {
                "ID1": record_pair[0]["ID"],
                "ID2": record_pair[1]["ID"],
                "decision": "duplicate",
            }
        )
        examples_buffer.insert(0, (record_pair, "match"))
        msg = (
            f"Marked as duplicate: {record_pair[0]['ID']} - "
            + f"{record_pair[1]['ID']}"
        )
        self.review_manager.report_logger.info(msg)

    def __active_label_no_duplicate(
        self,
        *,
        manual_dedupe_decision_list: typing.List[dict],
        record_pair: TrainingExample,
        examples_buffer: list,
    ) -> None:
        if not self.__manual:
            # Ensure that non-dupes do not exceed 3x dupes
            # (for balanced training data)
            if self.__n_distinct > self.__n_match * 3:
                examples_buffer.insert(0, (record_pair, "uncertain"))
                # continue

        manual_dedupe_decision_list.append(
            {
                "ID1": record_pair[0]["ID"],
                "ID2": record_pair[1]["ID"],
                "decision": "no_duplicate",
            }
        )
        examples_buffer.insert(0, (record_pair, "distinct"))
        msg = (
            f"Marked as non-duplicate: {record_pair[0]['ID']}"
            + f" - {record_pair[1]['ID']}"
        )
        self.review_manager.report_logger.info(msg)

    def __active_label_uncertain(
        self, *, examples_buffer: list, record_pair: TrainingExample
    ) -> None:
        examples_buffer.insert(0, (record_pair, "uncertain"))

    def __active_label_check_finished(
        self, *, manual_dedupe_decision_list: list
    ) -> bool:
        nr_duplicates = self.__get_nr_duplicates(
            result_list=manual_dedupe_decision_list
        )
        nr_non_duplicates = self.__get_nr_non_duplicates(
            result_list=manual_dedupe_decision_list
        )
        if not nr_duplicates > 30 or not nr_non_duplicates > 30:
            if "y" != input(
                "The machine-learning requires "
                "30 duplicates and 30 non-duplicates. "
                "Quit anyway [y,n]?"
            ):
                return False
        os.system("cls" if os.name == "nt" else "clear")
        print("Finished labeling")
        return True

    def __check_finised_labeling(
        self, *, examples_buffer: list, max_associations_to_check: int
    ) -> bool:
        self.__n_match = len(self.deduper.training_pairs["match"]) + sum(
            label == "match" for _, label in examples_buffer
        )
        self.__n_distinct = len(self.deduper.training_pairs["distinct"]) + sum(
            label == "distinct" for _, label in examples_buffer
        )
        if (self.__n_match + self.__n_distinct) > max_associations_to_check:
            return True
        return False

    def __mark_active_labeling_pairs(self, *, examples_buffer: list) -> None:
        if len(examples_buffer) > 1:  # Max number of previous operations
            record_pair, label = examples_buffer.pop()
            if label in {"distinct", "match"}:
                examples: TrainingData = {"distinct": [], "match": []}
                examples[label].append(record_pair)
                self.deduper.mark_pairs(examples)

    def __adapted_console_label_active_label(
        self,
        *,
        manual_dedupe_decision_list: list,
        max_associations_to_check: int,
        keys: list,
        uncertain_pairs: list,
    ) -> list[tuple[TrainingExample, typing.Literal["match", "distinct", "uncertain"]]]:
        examples_buffer: list[
            tuple[TrainingExample, typing.Literal["match", "distinct", "uncertain"]]
        ] = []
        finished, use_previous = False, False

        while not finished:
            record_pair = self.__get_record_pair_for_labeling(
                use_previous=use_previous,
                examples_buffer=examples_buffer,
                uncertain_pairs=uncertain_pairs,
            )
            if use_previous:
                use_previous = False

            finished = self.__check_finised_labeling(
                examples_buffer=examples_buffer,
                max_associations_to_check=max_associations_to_check,
            )

            user_input = "u"
            if self.__identical_colrev_ids(record_pair=record_pair):
                user_input = "y"
            else:
                # Check local_index for duplicate information
                curations_dupe_info = self.local_index.is_duplicate(
                    record1_colrev_id=record_pair[0]["colrev_id"].split(";"),
                    record2_colrev_id=record_pair[1]["colrev_id"].split(";"),
                )

                user_input = (
                    colrev.ops.built_in.dedupe.utils.console_duplicate_instance_label(
                        record_pair,
                        keys,
                        self.__manual,
                        curations_dupe_info,
                        self.__n_match,
                        self.__n_distinct,
                        examples_buffer,
                    )
                )

            if user_input == "y":
                self.__active_label_duplicate(
                    manual_dedupe_decision_list=manual_dedupe_decision_list,
                    record_pair=record_pair,
                    examples_buffer=examples_buffer,
                )

            elif user_input == "n":
                self.__active_label_no_duplicate(
                    manual_dedupe_decision_list=manual_dedupe_decision_list,
                    record_pair=record_pair,
                    examples_buffer=examples_buffer,
                )

            elif user_input == "u":
                self.__active_label_uncertain(
                    examples_buffer=examples_buffer, record_pair=record_pair
                )

            elif user_input == "f":
                finished = self.__active_label_check_finished(
                    manual_dedupe_decision_list=manual_dedupe_decision_list
                )
                if not finished:
                    continue

            elif user_input == "p":
                use_previous = True
                uncertain_pairs.append(record_pair)

            self.__mark_active_labeling_pairs(examples_buffer=examples_buffer)

        return examples_buffer

    def __adapted_console_label(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
        manual: bool,
        max_associations_to_check: int = 1000,
    ) -> None:
        """
        Train a matcher instance (Dedupe, RecordLink, or Gazetteer) from the cli.
        Example

        .. code:: python

        > deduper = dedupe.Dedupe(variables)
        > deduper.prepare_training(data)
        > dedupe.console_label(deduper)
        """

        dedupe_operation.review_manager.logger.info(
            "Note: duplicate associations available in the LocalIndex "
            "are applied automatically."
        )
        dedupe_operation.review_manager.logger.info("Press Enter to start.")
        input()
        self.__manual = manual

        keys = unique(
            field.field for field in self.deduper.data_model.primary_variables
        )

        uncertain_pairs: list[TrainingExample] = []
        manual_dedupe_decision_list: typing.List[dict] = []

        examples_buffer = self.__adapted_console_label_active_label(
            manual_dedupe_decision_list=manual_dedupe_decision_list,
            max_associations_to_check=max_associations_to_check,
            keys=keys,
            uncertain_pairs=uncertain_pairs,
        )

        for record_pair, label in examples_buffer:
            if label in ["distinct", "match"]:
                examples: typing.Dict[str, list] = {"distinct": [], "match": []}
                examples[label].append(record_pair)
                self.deduper.mark_pairs(examples)

        # Note : for debugging:
        # import csv
        # keys = manual_dedupe_decision_list[0].keys()
        # with open("manual_dedupe_decision_list.csv", "w", newline="") as output_file:
        #     dict_writer = csv.DictWriter(output_file, keys)
        #     dict_writer.writeheader()
        #     dict_writer.writerows(manual_dedupe_decision_list)

        # Apply and commit
        self.apply_active_learning(
            dedupe_operation=dedupe_operation,
            results=manual_dedupe_decision_list,
        )

    def run_dedupe(self, dedupe_operation: colrev.ops.dedupe.Dedupe) -> None:
        """Run the console labeling to train the active learning model"""

        # Setting in-memory mode depending on system RAM
        records_headers = dedupe_operation.review_manager.dataset.load_records_dict(
            header_only=True
        )
        sample_size = len(list(records_headers.values()))
        ram = psutil.virtual_memory().total
        in_memory = sample_size * 5000000 < ram

        self.setup_active_learning_dedupe(
            dedupe_operation=dedupe_operation, retrain=False, in_memory=in_memory
        )

        dedupe_io.console_label = self.__adapted_console_label
        dedupe_io.console_label(dedupe_operation=dedupe_operation, manual=True)


@zope.interface.implementer(colrev.env.package_manager.DedupePackageEndpointInterface)
@dataclass
class ActiveLearningDedupeAutomated(JsonSchemaMixin):
    """Applies trained (active learning) model"""

    settings: ActiveLearningSettings
    ci_supported: bool = False

    @dataclass
    class ActiveLearningSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for ActiveLearning"""

        endpoint: str
        merge_threshold: float = 0.8
        partition_threshold: float = 0.5

        _details = {
            "merge_threshold": {"tooltip": "Threshold for merging record pairs"},
            "partition_threshold": {"tooltip": "Threshold for partitioning"},
        }

    settings_class = ActiveLearningSettings

    def __init__(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,  # pylint: disable=unused-argument
        settings: dict,
    ):
        logging.basicConfig()
        logging.getLogger("dedupe.canopy_index").setLevel(logging.WARNING)

        self.settings = self.settings_class.load_settings(data=settings)

        self.settings_file = (
            dedupe_operation.review_manager.path
            / ActiveLearningDedupeTraining.SETTINGS_FILE_RELATIVE
        )

        assert self.settings.merge_threshold >= 0.0
        assert self.settings.merge_threshold <= 1.0
        assert self.settings.partition_threshold >= 0.0
        assert self.settings.partition_threshold <= 1.0

    def __get_duplicates_from_clusters(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe, clustered_dupes: list
    ) -> list[dict]:
        dedupe_operation.review_manager.report_logger.info(
            f"set merge_threshold: {self.settings.merge_threshold}"
        )
        dedupe_operation.review_manager.logger.info(
            f"set merge_threshold: {self.settings.merge_threshold}"
        )
        results = []
        dedupe_decision_list = []
        for cluster_id, (records, scores) in enumerate(clustered_dupes):
            dedupe_decision_list.append(
                {
                    "cluster_id": cluster_id,
                    "records": list(records),
                    "score": statistics.mean(list(scores)),
                }
            )

        for dedupe_decision in dedupe_decision_list:
            if len(dedupe_decision["records"]) == 0:
                continue

            if dedupe_decision["score"] < self.settings.merge_threshold:
                continue

            orig_rec = dedupe_decision["records"].pop()
            if 0 == len(dedupe_decision["records"]):
                results.append(
                    {
                        "ID1": orig_rec,
                        "decision": "no_duplicate",
                    }
                )
                continue

            for dupe_rec in dedupe_decision["records"]:
                orig_propagated = dedupe_operation.review_manager.dataset.propagated_id(
                    record_id=orig_rec
                )
                dupe_propagated = dedupe_operation.review_manager.dataset.propagated_id(
                    record_id=dupe_rec
                )

                if not orig_propagated and not dupe_propagated:
                    # Use the record['ID'] without appended letters if possible
                    # Set orig_propagated=True if record_a_ID should be kept
                    if orig_rec[-1:].isnumeric() and not dupe_rec[-1:].isnumeric():
                        orig_propagated = True
                    else:
                        dupe_propagated = True
                        # This arbitrarily uses record_b_ID
                        # if none of the IDs has a letter appended.

                    if orig_propagated and dupe_propagated:
                        # both_IDs_propagated
                        dedupe_operation.review_manager.logger.error(
                            f"Both IDs propagated: {orig_rec}, {dupe_rec}"
                        )
                        continue

                    if orig_propagated:
                        results.append(
                            {
                                "ID1": orig_rec,
                                "ID2": dupe_rec,
                                "decision": "duplicate",
                                "score": dedupe_decision["score"],
                            }
                        )

                    else:
                        results.append(
                            {
                                "ID1": dupe_rec,
                                "ID2": orig_rec,
                                "decision": "duplicate",
                                "score": dedupe_decision["score"],
                            }
                        )
        return results

    def __highlight_cells(self, input_df: pd.DataFrame) -> pd.DataFrame:  # type: ignore  # noqa
        dataframe = input_df.copy()
        dataframe["cluster_id"] = dataframe["cluster_id"].astype(str)
        dataframe.loc[:, dataframe.columns != "cluster_id"] = "background-color: white"

        # http://www.excelsupersite.com/what-are-the-56-colorindex-colors-in-excel/
        available_colors = [
            "#FFFFFF",
            "#FFCC99",
            "#FFFFCC",
            "#CCFFCC",
            "#FFFF99",
            "#99CCFF",
            "#FF99CC",
        ]
        cur_color_index = -1
        cur_cluster = ""

        prev_row: dict = {}
        for i, row in dataframe.iterrows():
            if row["cluster_id"] != cur_cluster:
                cur_color_index += 1
                cur_cluster = row["cluster_id"]
            # dataframe.at[i, 'cluster_id'] = ( # only the cluster_id column
            dataframe.at[i, :] = (
                "background-color: "
                + available_colors[cur_color_index % len(available_colors)]
            )

        for i, row in input_df.iterrows():
            if i in [0, 1]:
                continue
            if len(prev_row) != 0:
                for j, val in row.items():
                    # changes in these fields should not be marked
                    if j in ["error", "confidence_score", "ID"]:
                        continue
                    # do not mark changes between different clusters
                    if j == "cluster_id" and prev_row["cluster_id"] != val:
                        break
                    if val != prev_row[j]:
                        dataframe.at[i, j] = dataframe.at[i, j] + "; font-weight: bold"

            prev_row = row.to_dict()

        return dataframe

    def __export_duplicates_excel(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe, collected_duplicates: list
    ) -> None:
        if len(collected_duplicates) == 0:
            print("No duplicates found")
            return

        duplicates_df = pd.DataFrame.from_records(collected_duplicates)
        duplicates_df.fillna("", inplace=True)
        duplicates_df["distinct_str"] = (
            duplicates_df["author"]
            + duplicates_df["title"]
            + duplicates_df["year"]
            + duplicates_df["container_title"]
            + duplicates_df["volume"]
            + duplicates_df["number"]
            + duplicates_df["pages"]
        )
        # Only export bibliographically distict cases
        duplicates_df = duplicates_df.groupby("distinct_str").filter(
            lambda x: len(x) == 1
        )
        duplicates_df.drop(columns=["distinct_str"], inplace=True)

        duplicates_df = duplicates_df[
            [
                "error",
                "confidence_score",
                "cluster_id",
                "ID",
                "author",
                "title",
                "year",
                "container_title",
                "volume",
                "number",
                "pages",
            ]
        ]

        duplicates_df = duplicates_df.groupby("cluster_id").filter(lambda x: len(x) > 1)
        duplicates_df = duplicates_df.sort_values(
            ["confidence_score", "cluster_id"], ascending=(True, False)
        )
        duplicates_df["confidence_score"] = duplicates_df["confidence_score"].round(4)
        # to adjust column widths in ExcelWriter:
        # http://pandas-docs.github.io/pandas-docs-travis/user_guide/style.html
        duplicates_df.style.apply(self.__highlight_cells, axis=None)
        duplicates_df.to_excel(dedupe_operation.dupe_file, index=False)

    def __export_non_duplicates_excel(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
        collected_non_duplicates: list,
    ) -> None:
        if len(collected_non_duplicates) == 0:
            print("No duplicates.")
            return

        non_duplicates_df = pd.DataFrame.from_records(collected_non_duplicates)
        # To develop in jupyter:
        # non_duplicates_df.to_csv(output_file, index=False)
        # non_duplicates_df = pd.read_csv("duplicates_for_validation.csv")
        non_duplicates_df = non_duplicates_df[
            [
                "error",
                "cluster_id",
                "confidence_score",
                "ID",
                "author",
                "title",
                "year",
                "container_title",
                "volume",
                "number",
                "pages",
            ]
        ]
        non_duplicates_df = non_duplicates_df.groupby("cluster_id").filter(
            lambda x: len(x) > 1
        )
        non_duplicates_df = non_duplicates_df.sort_values(
            ["confidence_score", "cluster_id"], ascending=(True, False)
        )
        non_duplicates_df["confidence_score"] = non_duplicates_df[
            "confidence_score"
        ].round(4)
        # to adjust column widths in ExcelWriter:
        # http://pandas-docs.github.io/pandas-docs-travis/user_guide/style.html
        non_duplicates_df.style.apply(self.__highlight_cells, axis=None)
        non_duplicates_df.to_excel(dedupe_operation.non_dupe_file_xlsx, index=False)

    def __get_collected_dupes_non_dupes_from_clusters(
        self, *, clustered_dupes: list, data_d: dict
    ) -> dict:
        # pylint: disable=too-many-locals

        cluster_membership = {}
        # cluster_membership:
        # {'FrolovaFrolovKayurovEtAl2021': {'Cluster ID': 352, 'confidence_score': 1.0},
        #  'BhaskaraBawa2021': {'Cluster ID': 353, 'confidence_score': 1.0}}
        for cluster_id, (records, scores) in enumerate(clustered_dupes):
            for record_id, score in zip(records, scores):
                cluster_membership[record_id] = {
                    "cluster_id": cluster_id,
                    "confidence_score": score,
                }

        results: typing.Dict[str, list] = {
            "collected_duplicates": [],
            "collected_non_duplicates": [],
        }
        for cluster_id, vals in data_d.items():
            vals.update(error="")
            if cluster_id in cluster_membership:
                cur_cluster_membership = cluster_membership[cluster_id]
                vals.update(cur_cluster_membership)
                if (
                    cur_cluster_membership["confidence_score"]
                    > self.settings.merge_threshold
                ):
                    results["collected_duplicates"].append(vals)
                else:
                    results["collected_non_duplicates"].append(vals)

        # Set confidence scores to average of group
        for cluster_nr in {d["cluster_id"] for d in results["collected_duplicates"]}:
            avg_confidence = statistics.mean(
                [
                    d["confidence_score"]
                    for d in results["collected_duplicates"]
                    if d["cluster_id"] == cluster_nr
                ]
            )
            for collected_duplicate in results["collected_duplicates"]:
                if collected_duplicate["cluster_id"] == cluster_nr:
                    collected_duplicate["confidence_score"] = avg_confidence
        for cluster_nr in {
            d["cluster_id"] for d in results["collected_non_duplicates"]
        }:
            avg_confidence = statistics.mean(
                [
                    d["confidence_score"]
                    for d in results["collected_non_duplicates"]
                    if d["cluster_id"] == cluster_nr
                ]
            )
            for collected_non_duplicate in results["collected_non_duplicates"]:
                if collected_non_duplicate["cluster_id"] == cluster_nr:
                    collected_non_duplicate["confidence_score"] = avg_confidence

        return results

    def __export_validation_excel(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
        clustered_dupes: list,
        data_d: dict,
    ) -> None:
        results = self.__get_collected_dupes_non_dupes_from_clusters(
            clustered_dupes=clustered_dupes, data_d=data_d
        )

        self.__export_duplicates_excel(
            dedupe_operation=dedupe_operation,
            collected_duplicates=results["collected_duplicates"],
        )

        self.__export_non_duplicates_excel(
            dedupe_operation=dedupe_operation,
            collected_non_duplicates=results["collected_non_duplicates"],
        )

    def __cluster_duplicates(
        self, *, dedupe_operation: colrev.ops.dedupe.Dedupe, data_d: dict
    ) -> list:
        # pylint: disable=too-many-locals

        dedupe_operation.review_manager.logger.info("Clustering duplicates...")
        dedupe_operation.review_manager.logger.info(
            f"Number of records (before): {len(data_d.items())}"
        )

        # Setting in-memory mode depending on system RAM
        records_headers = dedupe_operation.review_manager.dataset.load_records_dict(
            header_only=True
        )
        sample_size = len(list(records_headers.values()))
        ram = psutil.virtual_memory().total
        in_memory = sample_size * 5000000 < ram

        with open(self.settings_file, "rb") as sett_file:
            deduper = dedupe_io.StaticDedupe(sett_file, num_cores=4)

        # `partition` will return sets of records that dedupe
        # believes are all referring to the same entity.

        if in_memory:
            dedupe_operation.review_manager.report_logger.info(
                f"set partition_threshold: {self.settings.partition_threshold}"
            )

            clustered_dupes = deduper.partition(
                data_d, self.settings.partition_threshold
            )

            # from dedupe.core import BlockingError
            # except BlockingError:

            #     dedupe_operation.review_manager.logger.info(
            #         "No duplicates found (please check carefully)"
            #     )
            #     dedupe_operation.apply_merges(results=[], complete_dedupe=True)
            #     dedupe_operation.review_manager.create_commit(
            #         msg="Merge duplicate records (no duplicates detected)",
            #     )
            #     dedupe_operation.review_manager.logger.info(
            #         "If there are errors, it could be necessary to remove the "
            #         ".records_dedupe_training.json to train a fresh dedupe model."
            #     )

            #     pass
            # except KeyboardInterrupt:
            #     print("KeyboardInterrupt")
            #     pass

        else:
            for field in deduper.fingerprinter.index_fields:
                field_data = (r[field] for r in data_d.values() if field in r)
                deduper.fingerprinter.index(field_data, field)

            full_data = ((r["ID"], r) for r in data_d.values())

            # pylint: disable=not-callable
            # fingerprinter is callable according to
            # https://github.com/dedupeio/dedupe/blob/
            # b9d8f111bcd5ffd177659f79f57354d9a9318359/dedupe/blocking.py
            b_data = deduper.fingerprinter(full_data)

            # use sqlite: light-weight, file-based
            # https://docs.python.org/3/library/sqlite3.html
            # https://dedupeio.github.io/dedupe-examples/docs/pgsql_big_dedupe_example.html

            dedupe_db = Path("dedupe.db")
            dedupe_db.unlink(missing_ok=True)
            con = sqlite3.connect(str(dedupe_db))

            cur = con.cursor()

            cur.execute("""DROP TABLE IF EXISTS blocking_map""")
            cur.execute("""CREATE TABLE blocking_map (block_key text, ID INTEGER)""")
            cur.executemany("""INSERT into blocking_map values (?, ?)""", b_data)

            records_data = {r["ID"]: r for r in data_d.values()}

            def record_pairs(result_set: list[tuple]) -> typing.Iterator[tuple]:
                for row in result_set:
                    id_a, id_b = row
                    record_a = (id_a, records_data[id_a])
                    record_b = (id_b, records_data[id_b])

                    yield record_a, record_b

            cur.execute(
                """select DISTINCT l.ID as east, r.ID as west
                        from blocking_map as l
                        INNER JOIN blocking_map as r
                        using (block_key)
                        where east != west"""
            )

            clustered_dupes = list(
                deduper.cluster(
                    deduper.score(record_pairs(cur.fetchall())), threshold=0.5
                )
            )

            # import csv
            # clusterin_results_csv = Path("clusterin_results.csv")
            # clusterin_results_csv.unlink(missing_ok=True)
            # with open(clusterin_results_csv, "w") as out:
            #     csv_out = csv.writer(out)
            #     csv_out.writerow(["ID1", "ID2", "conf"])
            #     for row in list(cluster_ids(clustered_dupes)):
            #         if row[0] != row[1]:  # only focus on non-identical IDs
            #             csv_out.writerow(row)

            con.commit()
            con.close()
            dedupe_db.unlink(missing_ok=True)

        dedupe_operation.review_manager.report_logger.info(
            f"Number of duplicate sets {len(clustered_dupes)}"
        )
        return clustered_dupes

    def run_dedupe(self, dedupe_operation: colrev.ops.dedupe.Dedupe) -> None:
        """Cluster potential duplicates, merge, and export validation tables"""

        if not self.settings_file.is_file():
            dedupe_operation.review_manager.logger.info(
                "No settings file. Skip ML-clustering."
            )
            return

        data_d = dedupe_operation.read_data()

        clustered_dupes = self.__cluster_duplicates(
            dedupe_operation=dedupe_operation, data_d=data_d
        )

        results = self.__get_duplicates_from_clusters(
            dedupe_operation=dedupe_operation, clustered_dupes=clustered_dupes
        )

        dedupe_operation.apply_merges(results=results, complete_dedupe=True)

        self.__export_validation_excel(
            dedupe_operation=dedupe_operation,
            clustered_dupes=clustered_dupes,
            data_d=data_d,
        )

        dedupe_operation.review_manager.create_commit(
            msg="Merge duplicate records (based on active-learning clusters)",
            script_call="colrev dedupe",
        )

        dedupe_operation.review_manager.logger.info(
            "Successfully completed the deduplication. Please check the "
            "duplicates_to_validate.xlsx and non_duplicates_to_validate.xlsx for "
            'potential errors.\nTo fix them, mark them in the "error" column and '
            "run\n  colrev dedupe --fix_errors\n\n"
        )

        if Path("same_source_merges.txt").is_file():
            dedupe_operation.review_manager.logger.info(
                "Detected and prevented same-source merges. Please check potential"
                "duplicates in same_source_merges.txt"
            )

        info = dedupe_operation.get_info()
        if len(info["same_source_merges"]) > 0:
            dedupe_operation.review_manager.logger.info(
                f"\n{colors.ORANGE}Same source merges to check:{colors.END}"
                "\n- ".join(info["same_source_merges"]) + "\n"
            )
        else:
            dedupe_operation.review_manager.logger.info(
                "\nNo same-origin merges detected."
            )


if __name__ == "__main__":
    pass
