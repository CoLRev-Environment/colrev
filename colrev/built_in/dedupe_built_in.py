#! /usr/bin/env python
from __future__ import annotations

import logging
import os
import time
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import zope.interface
from dacite import from_dict
from thefuzz import fuzz
from tqdm import tqdm

import colrev.built_in.pdf_prep
import colrev.cli_colors as colors
import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record


if TYPE_CHECKING:
    import dedupe as dedupe_io

# pylint: disable=too-many-arguments


def console_duplicate_instance_label(
    record_pair,
    keys,
    manual,
    index_dupe_info,
    n_match,
    n_distinct,
    examples_buffer,
) -> str:

    if manual:
        os.system("cls" if os.name == "nt" else "clear")

    if manual:
        colrev.record.Record.print_diff_pair(record_pair=record_pair, keys=keys)

    user_input = "unsure"
    if "yes" == index_dupe_info:
        user_input = "y"
        if manual:
            print(f"{n_match} positive, {n_distinct} negative")
            print("#")
            print("# index_dupe_info: yes/duplicate")
            print("#")
            # TODO : add option to validate explicitly  (Enter to confirm)
            time.sleep(0.6)
    elif "no" == index_dupe_info:
        user_input = "n"
        if manual:
            print(f"{n_match} positive, {n_distinct} negative")
            print("#")
            print("# index_dupe_info: no duplicate")
            print("#")
            # TODO : add option to validate explicitly  (Enter to confirm)
            time.sleep(0.6)
    else:
        if manual:
            print(f"{n_match} positive, {n_distinct} negative")

        if manual:
            valid_response = False
            user_input = ""

            while not valid_response:
                if examples_buffer:
                    prompt = (
                        "Duplicate? (y)es / (n)o / (u)nsure /"
                        + " (f)inished / (p)revious"
                    )
                    valid_responses = {"y", "n", "u", "f", "p"}
                else:
                    prompt = "Duplicate? (y)es / (n)o / (u)nsure / (f)inished"
                    valid_responses = {"y", "n", "u", "f"}

                print(prompt)
                user_input = input()
                if user_input in valid_responses:
                    valid_response = True
    return user_input


@dataclass
class SimpleDedupeSettings:
    name: str
    merging_non_dup_threshold: float
    merging_dup_threshold: float


@zope.interface.implementer(colrev.process.DedupeEndpoint)
class SimpleDedupeEndpoint:
    """Simple duplicate identification when the sample size is too small"""

    def __init__(self, *, dedupe_operation: colrev.dedupe.Dedupe, settings: dict):

        # Set default values (if necessary)
        if "merging_non_dup_threshold" not in settings:
            settings["merging_non_dup_threshold"] = 0.7
        if "merging_dup_threshold" not in settings:
            settings["merging_dup_threshold"] = 0.95

        self.settings = from_dict(data_class=SimpleDedupeSettings, data=settings)

        assert self.settings.merging_non_dup_threshold >= 0.0
        assert self.settings.merging_non_dup_threshold <= 1.0
        assert self.settings.merging_dup_threshold >= 0.0
        assert self.settings.merging_dup_threshold <= 1.0

    def __calculate_similarities_record(
        self, *, dedupe_operation: colrev.dedupe.Dedupe, records_df: pd.DataFrame
    ) -> list:

        # Note: per definition, similarities are needed relative to the last row.
        records_df["similarity"] = 0
        records_df["details"] = 0
        sim_col = records_df.columns.get_loc("similarity")
        details_col = records_df.columns.get_loc("details")
        for base_record_i in range(0, records_df.shape[0]):
            sim_details = colrev.record.Record.get_similarity_detailed(
                df_a=records_df.iloc[base_record_i], df_b=records_df.iloc[-1]
            )
            dedupe_operation.review_manager.report_logger.debug(
                f"Similarity score: {sim_details['score']}"
            )
            dedupe_operation.review_manager.report_logger.debug(sim_details["details"])

            records_df.iloc[base_record_i, sim_col] = sim_details["score"]
            records_df.iloc[base_record_i, details_col] = sim_details["details"]
        # Note: return all other records (not the comparison record/first row)
        # and restrict it to the ID, similarity and details
        ck_col = records_df.columns.get_loc("ID")
        sim_col = records_df.columns.get_loc("similarity")
        details_col = records_df.columns.get_loc("details")
        return records_df.iloc[:, [ck_col, sim_col, details_col]]

    def append_merges(
        self, *, dedupe_operation: colrev.dedupe.Dedupe, batch_item: dict
    ) -> dict:

        dedupe_operation.review_manager.logger.debug(
            f'append_merges {batch_item["record"]}'
        )

        records_df = batch_item["queue"]

        # if the record is the first one added to the records
        # (in a preceding processing step), it can be propagated
        # if len(batch_item["queue"]) < 2:
        if len(records_df.index) < 2:
            return {
                "ID1": batch_item["record"],
                "ID2": "NA",
                "similarity": 1,
                "decision": "no_duplicate",
            }

        # df to get_similarities for each other record
        records_df = self.__calculate_similarities_record(
            dedupe_operation=dedupe_operation, records_df=records_df
        )
        # drop the first row (similarities are calculated relative to the last row)
        records_df = records_df.iloc[:-1, :]
        # if batch_item['record'] == 'AdamsNelsonTodd1992':
        #     records_df.to_csv('last_similarities.csv')

        max_similarity = records_df.similarity.max()

        # TODO: it may not be sufficient to consider
        # the record with the highest similarity

        ret = {}
        if max_similarity <= self.settings.merging_non_dup_threshold:
            # Note: if no other record has a similarity exceeding the threshold,
            # it is considered a non-duplicate (in relation to all other records)
            dedupe_operation.review_manager.logger.debug(
                f"max_similarity ({max_similarity})"
            )
            ret = {
                "ID1": batch_item["record"],
                "ID2": "NA",
                "similarity": max_similarity,
                "decision": "no_duplicate",
            }

        elif (
            self.settings.merging_non_dup_threshold
            < max_similarity
            < self.settings.merging_dup_threshold
        ):

            other_id = records_df.loc[records_df["similarity"].idxmax()]["ID"]
            dedupe_operation.review_manager.logger.debug(
                f"max_similarity ({max_similarity}): {batch_item['record']} {other_id}"
            )
            details = records_df.loc[records_df["similarity"].idxmax()]["details"]
            dedupe_operation.review_manager.logger.debug(details)
            # record_a, record_b = sorted([ID, record["ID"]])
            msg = (
                f'{batch_item["record"]} - {other_id}'.ljust(35, " ")
                + f"  - potential duplicate (similarity: {max_similarity})"
            )
            dedupe_operation.review_manager.report_logger.info(msg)
            dedupe_operation.review_manager.logger.info(msg)
            ret = {
                "ID1": batch_item["record"],
                "ID2": other_id,
                "similarity": max_similarity,
                "decision": "potential_duplicate",
            }

        else:  # max_similarity >= self.settings.merging_dup_threshold:
            # note: the following status will not be saved in the bib file but
            # in the duplicate_tuples.csv (which will be applied to the bib file
            # in the end)
            other_id = records_df.loc[records_df["similarity"].idxmax()]["ID"]
            dedupe_operation.review_manager.logger.debug(
                f"max_similarity ({max_similarity}): {batch_item['record']} {other_id}"
            )
            details = records_df.loc[records_df["similarity"].idxmax()]["details"]
            dedupe_operation.review_manager.logger.debug(details)
            msg = (
                f'Dropped duplicate: {batch_item["record"]} (duplicate of {other_id})'
                + f" (similarity: {max_similarity})\nDetails: {details}"
            )
            dedupe_operation.review_manager.report_logger.info(msg)
            dedupe_operation.review_manager.logger.info(msg)
            ret = {
                "ID1": batch_item["record"],
                "ID2": other_id,
                "similarity": max_similarity,
                "decision": "duplicate",
            }
        return ret

    # TODO : add similarity function as a parameter?
    def run_dedupe(self, dedupe_operation: colrev.dedupe.Dedupe) -> None:
        """Pairwise identification of duplicates based on static similarity measure

        This procedure should only be used in small samples on which active learning
        models cannot be trained.
        """

        pd.options.mode.chained_assignment = None  # default='warn'

        saved_args = locals()

        dedupe_operation.review_manager.logger.info("Simple duplicate identification")

        dedupe_operation.review_manager.logger.info(
            "Pairwise identification of duplicates based on static similarity measure"
        )

        # Note: this would also be a place to set
        # records as "no-duplicate" by definition
        # (e.g., for non-duplicated sources marked in the sources)

        record_state_list = (
            dedupe_operation.review_manager.dataset.get_record_state_list()
        )
        ids_to_dedupe = [
            x["ID"]
            for x in record_state_list
            if x["colrev_status"] == str(colrev.record.RecordState.md_prepared)
        ]
        processed_ids = [
            x["ID"]
            for x in record_state_list
            if x["colrev_status"]
            not in [
                str(colrev.record.RecordState.md_imported),
                str(colrev.record.RecordState.md_prepared),
                str(colrev.record.RecordState.md_needs_manual_preparation),
            ]
        ]
        if len(ids_to_dedupe) > 20:
            if not dedupe_operation.review_manager.force_mode:
                dedupe_operation.review_manager.logger.warning(
                    "Simple duplicate identification selected despite sufficient sample size.\n"
                    "Active learning algorithms may perform better:\n"
                    f"{colors.ORANGE}   colrev settings -m 'dedupe.scripts="
                    '[{"endpoint": "active_learning_training"},'
                    f'{{"endpoint": "active_learning_automated"}}]\'{colors.END}'
                )
                dedupe_operation.review_manager.logger.info(
                    "To use simple duplicate identification, use\n"
                    f"{colors.ORANGE}    colrev dedupe --force{colors.END}"
                )
                return

        nr_tasks = len(ids_to_dedupe)
        dedupe_data = {
            "nr_tasks": nr_tasks,
            "queue": processed_ids + ids_to_dedupe,
            "items_start": len(processed_ids),
        }
        dedupe_operation.review_manager.logger.debug(
            dedupe_operation.review_manager.p_printer.pformat(dedupe_data)
        )

        # the queue (order) matters for the incremental merging (make sure that each
        # additional record is compared to/merged with all prior records in
        # the queue)

        records = dedupe_operation.review_manager.dataset.load_records_dict()

        # Note: Because we only introduce individual (non-merged records),
        # there should be no semicolons in colrev_origin!
        records_queue = [
            record
            for ID, record in records.items()
            if ID in dedupe_data["queue"]  # type: ignore
        ]

        records_df_queue = pd.DataFrame.from_dict(records_queue)
        records = dedupe_operation.prep_records(records_df=records_df_queue)
        # dedupe.review_manager.p_printer.pprint(records.values())
        records_df = pd.DataFrame(records.values())

        items_start = dedupe_data["items_start"]
        batch_data = []
        for i in range(items_start, len(dedupe_data["queue"])):  # type: ignore
            batch_data.append(
                {
                    "record": dedupe_data["queue"][i],  # type: ignore
                    "queue": records_df.iloc[: i + 1],
                }
            )

        dedupe_batch_results = []
        for item in batch_data:
            dedupe_batch_results.append(
                self.append_merges(dedupe_operation=dedupe_operation, batch_item=item)
            )

        # dedupe_batch[-1]['queue'].to_csv('last_records.csv')

        dedupe_operation.apply_merges(results=dedupe_batch_results)

        dedupe_operation.review_manager.logger.info("Completed application of merges")

        potential_duplicates = [
            r for r in dedupe_batch_results if "potential_duplicate" == r["decision"]
        ]

        records = dedupe_operation.review_manager.dataset.load_records_dict()

        records_df_queue = pd.DataFrame.from_dict(records.values())
        records = dedupe_operation.prep_records(records_df=records_df_queue)
        # dedupe.review_manager.p_printer.pprint(records.values())
        records_df = pd.DataFrame(records.values())

        dedupe_operation.review_manager.create_commit(
            msg="Merge duplicate records",
            script_call="colrev dedupe",
            saved_args=saved_args,
        )

        keys = list(records_df.columns)
        for key_to_drop in [
            "ID",
            "colrev_origin",
            "colrev_status",
            "colrev_id",
            "container_title",
        ]:
            if key_to_drop in keys:
                keys.remove(key_to_drop)

        n_match, n_distinct = 0, 0
        for potential_duplicate in potential_duplicates:
            rec1 = records_df.loc[records_df["ID"] == potential_duplicate["ID1"], :]
            rec2 = records_df.loc[records_df["ID"] == potential_duplicate["ID2"], :]

            record_pair = [rec1.to_dict("records")[0], rec2.to_dict("records")[0]]

            user_input = console_duplicate_instance_label(
                record_pair, keys, True, "TODO", n_match, n_distinct, None
            )

            # set potential_duplicates
            if "y" == user_input:
                potential_duplicate["decision"] = "duplicate"
                n_match += 1
            if "n" == user_input:
                potential_duplicate["decision"] = "no_duplicate"
                n_distinct += 1

        # apply:
        dedupe_operation.apply_merges(results=potential_duplicates)

        # add and commit
        dedupe_operation.review_manager.dataset.add_record_changes()
        dedupe_operation.review_manager.create_commit(
            msg="Manual labeling of remaining duplicate candidates",
            manual_author=False,
            script_call="colrev dedupe",
            saved_args=saved_args,
        )


# # Active-learning deduplication

# # Note: code based on
# # https://github.com/dedupeio/dedupe-examples/blob/master/csv_example/csv_example.py


@zope.interface.implementer(colrev.process.DedupeEndpoint)
class ActiveLearningDedupeTrainingEndpoint:

    deduper: dedupe_io.Deduper

    def __init__(self, *, dedupe_operation: colrev.dedupe.Dedupe, settings: dict):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def setup_active_learning_dedupe(
        self, *, dedupe_operation: colrev.dedupe.Dedupe, retrain: bool, in_memory: bool
    ) -> None:
        """Prepare data for active learning setup"""
        # pylint: disable=import-outside-toplevel
        import dedupe as dedupe_io
        import random

        logging.getLogger("opensearch").setLevel(logging.ERROR)
        logging.getLogger("dedupe.training").setLevel(logging.WARNING)
        logging.getLogger("dedupe.api").setLevel(logging.WARNING)
        # logging.getLogger("rlr.crossvalidation:optimum").setLevel(logging.WARNING)

        if retrain:
            # Note : removing the training_file would be to start from scratch...
            # self.training_file.unlink(missing_ok=True)
            dedupe_operation.settings_file.unlink(missing_ok=True)

        dedupe_operation.review_manager.logger.info("Importing data ...")

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
            max_training_sample_size = min(3000, len(list(data_d.keys())))
            dedupe_operation.review_manager.logger.info(
                f"Selecting a random sample of {max_training_sample_size}"
                " to avoid memory problems"
            )
            # TODO : consider similar proportions of post-md_processed/md_prepared?
            keys = random.sample(list(data_d.keys()), max_training_sample_size)
            data_d = {key: data_d[key] for key in keys}

        dedupe_operation.review_manager.logger.debug(
            dedupe_operation.review_manager.p_printer.pformat(data_d)
        )

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

        # TODO : creating a corpus from all fields may create memory issues...

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
                "crf": True,
            },
            {
                "field": "container_title",
                "variable name": "container_title",
                "type": "ShortString",
                # "corpus": container_corpus(),
                "crf": True,
            },
            {"field": "year", "variable name": "year", "type": "DateTime"},
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
                f"{colors.ORANGE}  colrev settings -m 'dedupe.scripts="
                f'[{{"endpoint":"simple_dedupe"}}]\'{colors.END}'
            )

        if dedupe_operation.training_file.is_file():
            dedupe_operation.review_manager.logger.info(
                "Reading pre-labeled training data from "
                f"{dedupe_operation.training_file.name} "
                "and preparing data"
            )
            with open(dedupe_operation.training_file, "rb") as file:
                self.deduper.prepare_training(data_d, file)
        else:
            self.deduper.prepare_training(data_d)

        # TODO  input('del data_d - check memory')
        del data_d

        dedupe_operation.review_manager.logger.info(
            "Reading and preparation completed."
        )

    def apply_active_learning(
        self, *, dedupe_operation: colrev.dedupe.Dedupe, results: list, saved_args: dict
    ) -> None:

        dedupe_operation.apply_manual_deduplication_decisions(results=results)

        # Using the examples we just labeled, train the deduper and learn
        # blocking predicates
        self.deduper.train(recall=0.9, index_predicates=True)
        # print(self.deduper.data_model._field_comparators)
        # print(self.deduper.predicates)

        # When finished, save our training to disk
        with open(dedupe_operation.training_file, "w", encoding="utf-8") as train_file:
            self.deduper.write_training(train_file)
        dedupe_operation.review_manager.dataset.add_changes(
            path=dedupe_operation.training_file
        )

        # Save our weights and predicates to disk.  If the settings file
        # exists, we will skip all the training and learning next time we run
        # this file.
        with open(dedupe_operation.settings_file, "wb") as sett_file:
            self.deduper.write_settings(sett_file)

        dedupe_operation.review_manager.create_commit(
            msg="Labeling of duplicates (active learning)",
            manual_author=True,
            script_call="colrev dedupe",
            saved_args=saved_args,
        )
        # self.cleanup_training()

    def adapted_console_label(
        self,
        *,
        dedupe_operation: colrev.dedupe.Dedupe,
        manual: bool,
        saved_args: dict,
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

        # pylint: disable=import-outside-toplevel
        from dedupe._typing import TrainingData
        from dedupe._typing import RecordDictPair as TrainingExample

        # from dedupe._typing import TrainingExample
        from dedupe.core import unique

        dedupe_operation.review_manager.logger.info(
            "Note: duplicate associations available in the LocalIndex "
            "are applied automatically."
        )
        dedupe_operation.review_manager.logger.info("Press Enter to start.")
        input()

        local_index = dedupe_operation.review_manager.get_local_index()
        finished = False
        use_previous = False
        keys = unique(
            field.field for field in self.deduper.data_model.primary_variables
        )

        buffer_len = 1  # Max number of previous operations
        examples_buffer: list[
            tuple[TrainingExample, typing.Literal["match", "distinct", "uncertain"]]
        ] = []
        uncertain_pairs: list[TrainingExample] = []

        manual_dedupe_decision_list = []

        while not finished:

            if use_previous:
                record_pair, _ = examples_buffer.pop(0)
                use_previous = False
            else:
                try:
                    if not uncertain_pairs:
                        uncertain_pairs = self.deduper.uncertain_pairs()

                    record_pair = uncertain_pairs.pop()
                except IndexError:
                    break

            n_match = len(self.deduper.training_pairs["match"]) + sum(
                label == "match" for _, label in examples_buffer
            )
            n_distinct = len(self.deduper.training_pairs["distinct"]) + sum(
                label == "distinct" for _, label in examples_buffer
            )
            if (n_match + n_distinct) > max_associations_to_check:
                finished = True

            user_input = "u"
            if (
                record_pair[0]["colrev_id"] == record_pair[1]["colrev_id"]
                # if any of the colrev_ids NA,
                # we don't know whether we have a duplicate.
                and "NA" != record_pair[0]["colrev_id"]
                and "NA" != record_pair[1]["colrev_id"]
            ):
                user_input = "y"
            else:
                # Check local_index for duplicate information
                index_dupe_info = local_index.is_duplicate(
                    record1_colrev_id=record_pair[0]["colrev_id"].split(";"),
                    record2_colrev_id=record_pair[1]["colrev_id"].split(";"),
                )

                user_input = console_duplicate_instance_label(
                    record_pair,
                    keys,
                    manual,
                    index_dupe_info,
                    n_match,
                    n_distinct,
                    examples_buffer,
                )

            if user_input == "y":
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
                dedupe_operation.review_manager.report_logger.info(msg)

            elif user_input == "n":
                if not manual:
                    # Ensure that non-dupes do not exceed 3x dupes
                    # (for balanced training data)
                    if n_distinct > n_match * 3:
                        examples_buffer.insert(0, (record_pair, "uncertain"))
                        continue

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
                dedupe_operation.review_manager.report_logger.info(msg)

            elif user_input == "u":
                examples_buffer.insert(0, (record_pair, "uncertain"))
            elif user_input == "f":
                os.system("cls" if os.name == "nt" else "clear")
                print("Finished labeling")
                finished = True
            elif user_input == "p":
                use_previous = True
                uncertain_pairs.append(record_pair)

            if len(examples_buffer) > buffer_len:
                record_pair, label = examples_buffer.pop()
                if label in {"distinct", "match"}:
                    examples: TrainingData = {"distinct": [], "match": []}
                    examples[label].append(record_pair)
                    self.deduper.mark_pairs(examples)

        for record_pair, label in examples_buffer:
            if label in ["distinct", "match"]:
                examples = {"distinct": [], "match": []}
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
            saved_args=saved_args,
        )

    def run_dedupe(self, dedupe_operation: colrev.dedupe.Dedupe) -> None:

        # def run_active_learning_dedupe(
        #     *,
        #     dedupe,
        #     saved_args,
        #     in_memory: bool = True,
        # ) -> None:

        # pylint: disable=import-outside-toplevel
        import dedupe as dedupe_io

        # TODO : add something?
        saved_args: dict = {}
        in_memory = True

        self.setup_active_learning_dedupe(
            dedupe_operation=dedupe_operation, retrain=False, in_memory=in_memory
        )

        # if dedupe_operation.skip_training and dedupe_operation.settings_file.is_file():
        #     dedupe_operation.review_manager.report_logger\
        #       .info(f"Reading model from {dedupe_operation.settings_file.name}")
        #     with open(dedupe_operation.settings_file, "rb") as f:
        #         deduper = dedupe_operation.StaticDedupe(f)
        # else:

        # Active learning
        dedupe_io.console_label = self.adapted_console_label
        dedupe_io.console_label(
            dedupe_operation=dedupe_operation, manual=True, saved_args=saved_args
        )

        # Cluster remaining tuples
        # self.cluster_tuples(
        #     in_memory=in_memory,
        #     saved_args=saved_args,
        # )


@dataclass
class ActiveLearningSettings:
    name: str
    merge_threshold: float
    partition_threshold: float


@zope.interface.implementer(colrev.process.DedupeEndpoint)
class ActiveLearningDedupeAutomatedEndpoint:
    def __init__(self, *, dedupe_operation: colrev.dedupe.Dedupe, settings: dict):

        # Set default values (if necessary)
        if "merge_threshold" not in settings:
            settings["merge_threshold"] = 0.8
        if "partition_threshold" not in settings:
            settings["partition_threshold"] = 0.5

        self.settings = from_dict(data_class=ActiveLearningSettings, data=settings)

        assert self.settings.merge_threshold >= 0.0
        assert self.settings.merge_threshold <= 1.0
        assert self.settings.partition_threshold >= 0.0
        assert self.settings.partition_threshold <= 1.0

    def run_dedupe(self, dedupe_operation: colrev.dedupe.Dedupe) -> None:
        """Cluster potential duplicates, merge, and export validation spreadsheets"""

        # pylint: disable=import-outside-toplevel
        import statistics

        # TODO : CHECK:
        import dedupe as dedupe_io
        import sqlite3
        import psutil

        # Setting in-memory mode depending on system ram

        record_state_list = (
            dedupe_operation.review_manager.dataset.get_record_state_list()
        )
        sample_size = len(record_state_list)

        ram = psutil.virtual_memory().total
        in_memory = True
        if sample_size * 5000000 > ram:
            # Sample size too large
            in_memory = False

        saved_args: dict = {}

        with open(dedupe_operation.settings_file, "rb") as sett_file:
            deduper = dedupe_io.StaticDedupe(sett_file, num_cores=4)

        dedupe_operation.review_manager.logger.info("Clustering duplicates...")

        data_d = dedupe_operation.read_data()
        dedupe_operation.review_manager.logger.info(
            f"Number of records (before): {len(data_d.items())}"
        )

        # `partition` will return sets of records that dedupe
        # believes are all referring to the same entity.

        saved_args.update(merge_threshold=str(self.settings.merge_threshold))
        saved_args.update(partition_threshold=str(self.settings.partition_threshold))

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
            #     dedupe_operation.apply_merges(results=[], remaining_non_dupe=True)
            #     dedupe_operation.review_manager.create_commit(
            #         msg="Merge duplicate records (no duplicates detected)",
            #         script_call="colrev dedupe",
            #         saved_args=saved_args,
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

            def record_pairs(result_set):

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
        # Results
        cluster_membership = {}
        dedupe_decision_list = []
        for cluster_id, (records, scores) in enumerate(clustered_dupes):
            dedupe_decision_list.append(
                {
                    "cluster_id": cluster_id,
                    "records": list(records),
                    "score": statistics.mean(list(scores)),
                }
            )
            for record_id, score in zip(records, scores):

                cluster_membership[record_id] = {
                    "cluster_id": cluster_id,
                    "confidence_score": score,
                }

        # cluster_membership:
        # {'FrolovaFrolovKayurovEtAl2021': {'Cluster ID': 352, 'confidence_score': 1.0},
        #  'BhaskaraBawa2021': {'Cluster ID': 353, 'confidence_score': 1.0}}

        auto_dedupe = []
        id_list = []
        dedupe_operation.review_manager.report_logger.info(
            f"set merge_threshold: {self.settings.merge_threshold}"
        )
        dedupe_operation.review_manager.logger.info(
            f"set merge_threshold: {self.settings.merge_threshold}"
        )
        for dedupe_decision in dedupe_decision_list:

            if len(dedupe_decision["records"]) > 1:
                if dedupe_decision["score"] > self.settings.merge_threshold:
                    orig_rec = dedupe_decision["records"].pop()
                    id_list.append(orig_rec)
                    if 0 == len(dedupe_decision["records"]):
                        auto_dedupe.append(
                            {
                                "ID1": orig_rec,
                                "decision": "no_duplicate",
                            }
                        )
                        continue

                    for dupe_rec in dedupe_decision["records"]:

                        orig_propagated = (
                            dedupe_operation.review_manager.dataset.propagated_id(
                                record_id=orig_rec
                            )
                        )
                        dupe_propagated = (
                            dedupe_operation.review_manager.dataset.propagated_id(
                                record_id=dupe_rec
                            )
                        )

                        if not orig_propagated and not dupe_propagated:

                            # Use the record['ID'] without appended letters if possible
                            # Set orig_propagated=True if record_a_ID should be kept
                            if (
                                orig_rec[-1:].isnumeric()
                                and not dupe_rec[-1:].isnumeric()
                            ):
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
                                auto_dedupe.append(
                                    {
                                        "ID1": orig_rec,
                                        "ID2": dupe_rec,
                                        "decision": "duplicate",
                                        "score": dedupe_decision["score"],
                                    }
                                )

                            else:
                                auto_dedupe.append(
                                    {
                                        "ID1": dupe_rec,
                                        "ID2": orig_rec,
                                        "decision": "duplicate",
                                        "score": dedupe_decision["score"],
                                    }
                                )

        dedupe_operation.apply_merges(results=auto_dedupe, remaining_non_dupe=True)

        dedupe_operation.review_manager.reorder_log(
            ids=id_list, criterion="descending_thresholds"
        )

        # Export excels for validation
        def highlight_cells(input_df):
            dataframe = input_df.copy()
            dataframe["cluster_id"] = dataframe["cluster_id"].astype(str)
            dataframe.loc[
                :, dataframe.columns != "cluster_id"
            ] = "background-color: white"

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

            prev_row = {}
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
                            dataframe.at[i, j] = (
                                dataframe.at[i, j] + "; font-weight: bold"
                            )

                prev_row = row

            return dataframe

        collected_duplicates = []
        collected_non_duplicates = []
        for cluster_id, vals in data_d.items():
            vals.update(error="")
            if cluster_id in cluster_membership:
                cur_cluster_membership = cluster_membership[cluster_id]
                vals.update(cur_cluster_membership)
                if (
                    cur_cluster_membership["confidence_score"]
                    > self.settings.merge_threshold
                ):
                    collected_duplicates.append(vals)
                else:
                    collected_non_duplicates.append(vals)

        # Set confidence scores to average of group
        for cluster_nr in {d["cluster_id"] for d in collected_duplicates}:
            avg_confidence = statistics.mean(
                [
                    d["confidence_score"]
                    for d in collected_duplicates
                    if d["cluster_id"] == cluster_nr
                ]
            )
            for collected_duplicate in collected_duplicates:
                if collected_duplicate["cluster_id"] == cluster_nr:
                    collected_duplicate["confidence_score"] = avg_confidence
        for cluster_nr in {d["cluster_id"] for d in collected_non_duplicates}:
            avg_confidence = statistics.mean(
                [
                    d["confidence_score"]
                    for d in collected_non_duplicates
                    if d["cluster_id"] == cluster_nr
                ]
            )
            for collected_non_duplicate in collected_non_duplicates:
                if collected_non_duplicate["cluster_id"] == cluster_nr:
                    collected_non_duplicate["confidence_score"] = avg_confidence

        if len(collected_duplicates) == 0:
            print("No duplicates found")
        else:
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

            duplicates_df = duplicates_df.groupby("cluster_id").filter(
                lambda x: len(x) > 1
            )
            duplicates_df = duplicates_df.sort_values(
                ["confidence_score", "cluster_id"], ascending=(True, False)
            )
            duplicates_df["confidence_score"] = duplicates_df["confidence_score"].round(
                4
            )
            # to adjust column widths in ExcelWriter:
            # http://pandas-docs.github.io/pandas-docs-travis/user_guide/style.html
            duplicates_df = duplicates_df.style.apply(highlight_cells, axis=None)
            duplicates_df.to_excel(dedupe_operation.dupe_file, index=False)

            if len(collected_non_duplicates) > 0:
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
                non_duplicates_df = non_duplicates_df.style.apply(
                    highlight_cells, axis=None
                )
                non_duplicates_df.to_excel(
                    dedupe_operation.non_dupe_file_xlsx, index=False
                )

        dedupe_operation.review_manager.create_commit(
            msg="Merge duplicate records (based on active-learning clusters)",
            script_call="colrev dedupe",
            saved_args=saved_args,
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


@dataclass
class CurationDedupeSettings:
    name: str
    selected_source: str


@zope.interface.implementer(colrev.process.DedupeEndpoint)
class CurationDedupeEndpoint:
    """Deduplication endpoint for curations with full journals/proceedings
    retrieved from different sources (identifying duplicates in groups of
    volumes/issues or years)"""

    def __init__(self, *, dedupe_operation: colrev.dedupe.Dedupe, settings: dict):
        # TODO : the settings could be used
        # to select the specific files/grouping properties?!
        # -> see selected_source.
        # TODO : validate whether selected_source is in SOURCES.filenames
        self.settings = from_dict(data_class=CurationDedupeSettings, data=settings)

    def run_dedupe(self, dedupe_operation: colrev.dedupe.Dedupe) -> None:
        def get_similarity(df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:

            author_similarity = fuzz.ratio(df_a["author"], df_b["author"]) / 100

            title_similarity = (
                fuzz.ratio(df_a["title"].lower(), df_b["title"].lower()) / 100
            )

            # Note : the toc-based processing means that we are robust against
            # outlet, year, volume, number variations!
            weights = [0.4, 0.6]
            similarities = [
                author_similarity,
                title_similarity,
            ]

            weighted_average = sum(
                similarities[g] * weights[g] for g in range(len(similarities))
            )

            similarity_score = round(weighted_average, 4)

            return similarity_score

        def calculate_similarities(similarity_array, references, min_similarity):

            # Fill out the similarity matrix first
            for base_entry_i in range(1, references.shape[0]):
                for comparison_entry_i in range(1, references.shape[0]):
                    if base_entry_i > comparison_entry_i:
                        if -1 != similarity_array[base_entry_i, comparison_entry_i]:
                            similarity_array[
                                base_entry_i, comparison_entry_i
                            ] = get_similarity(
                                references.iloc[base_entry_i],
                                references.iloc[comparison_entry_i],
                            )

            tuples_to_process = []
            maximum_similarity = 1
            while True:

                maximum_similarity = np.amax(similarity_array)
                if maximum_similarity < min_similarity:
                    break
                result = np.where(similarity_array == np.amax(similarity_array))
                list_of_coordinates = list(zip(result[0], result[1]))
                for cord in list_of_coordinates:
                    similarity_array[cord] = 0  # ie., has been processed
                    tuples_to_process.append(
                        [
                            references.iloc[cord[0]]["ID"],
                            references.iloc[cord[1]]["ID"],
                            maximum_similarity,
                            "not_processed",
                        ]
                    )

            return similarity_array, tuples_to_process

        def get_toc_items(*, records_list: list) -> list:
            toc_items = []
            for record in records_list:
                # if record["colrev_status"] in [
                #     RecordState.md_imported,
                #     RecordState.md_needs_manual_preparation,
                #     RecordState.md_prepared,
                # ]:
                #     continue
                toc_item = {}
                if "article" == record["ENTRYTYPE"]:
                    if "journal" in record:
                        toc_item["journal"] = record["journal"]
                    if "volume" in record:
                        toc_item["volume"] = record["volume"]
                    if "number" in record:
                        toc_item["number"] = record["number"]

                if "inproceedings" == record["ENTRYTYPE"]:
                    if "booktitle" in record:
                        toc_item["booktitle"] = record["booktitle"]
                        toc_item["year"] = record["year"]
                if len(toc_item) > 0:
                    toc_items.append(toc_item)

            temp = {tuple(sorted(sub.items())) for sub in toc_items}
            toc_items = list(map(dict, temp))  # type: ignore
            return toc_items

        records = dedupe_operation.review_manager.dataset.load_records_dict()

        for record in records.values():
            if "container_title" not in record:
                record["container_title"] = (
                    record.get("journal", "")
                    + record.get("booktitle", "")
                    + record.get("series", "")
                )
            if "title" not in record:
                record["title"] = ""
            if "author" not in record:
                record["author"] = ""
            if "year" not in record:
                record["year"] = ""
            if "journal" not in record:
                record["journal"] = ""
            if "volume" not in record:
                record["volume"] = ""
            if "number" not in record:
                record["number"] = ""
            if "pages" not in record:
                record["pages"] = ""
            if "booktitle" not in record:
                record["booktitle"] = ""

        # first_source should be the highest quality source
        # (which moves to md_processed first)
        first_source = (
            self.settings.selected_source
            == dedupe_operation.review_manager.settings.dedupe.scripts[0][
                "selected_source"
            ]
        )

        # warn if not all SOURCE.filenames are included in a dedupe script
        if first_source:
            available_sources = [
                str(s.filename)
                for s in dedupe_operation.review_manager.settings.sources
            ]
            dedupe_sources = [
                s["selected_source"]
                for s in dedupe_operation.review_manager.settings.dedupe.scripts
                if "curation_full_outlet_dedupe" == s["endpoint"]
            ]
            sources_missing_in_dedupe = [
                x for x in available_sources if x not in dedupe_sources
            ]
            if len(sources_missing_in_dedupe) > 0:
                dedupe_operation.review_manager.logger.warning(
                    f"{colors.ORANGE}Sources missing in "
                    "dedupe.scripts.curation_full_outlet_dedupe: "
                    f"{','.join(sources_missing_in_dedupe)}{colors.END}"
                )
                if "y" == input("Add sources [y,n]?"):
                    for source_missing_in_dedupe in sources_missing_in_dedupe:
                        penultimate_position = (
                            len(dedupe_operation.review_manager.settings.dedupe.scripts)
                            - 1
                        )
                        dedupe_script_to_add = {
                            "endpoint": "curation_full_outlet_dedupe",
                            "selected_source": source_missing_in_dedupe,
                        }
                        dedupe_operation.review_manager.settings.dedupe.scripts.insert(
                            penultimate_position, dedupe_script_to_add
                        )
                        dedupe_operation.review_manager.save_settings()
                        dedupe_operation.review_manager.logger.info(
                            f"{colors.GREEN}Added {source_missing_in_dedupe} "
                            f"to dedupe.scripts{colors.END}"
                        )

        # TODO : create a search/retrieval script that retrieves
        # records based on linked attributes (see cml_assistant)

        source_records = [
            r
            for r in records.values()
            if r["colrev_status"] == colrev.record.RecordState.md_prepared
            and self.settings.selected_source.replace("search/", "")
            in r["colrev_origin"]
        ]

        toc_items = get_toc_items(records_list=source_records)

        if first_source:

            dedupe_operation.review_manager.logger.info(
                f"Starting with records from {self.settings.selected_source}"
                " (setting to md_processed as the initial records)"
            )

            for toc_item in toc_items:

                # Note : these would be potential errors (duplicates)
                # because they have the same selected_source
                processed_same_toc_same_source_records = [
                    r
                    for r in records.values()
                    if all(r.get(k, "NA") == v for k, v in toc_item.items())
                    and r["colrev_status"]
                    not in [
                        colrev.record.RecordState.md_prepared,
                        colrev.record.RecordState.md_needs_manual_preparation,
                        colrev.record.RecordState.md_imported,
                        colrev.record.RecordState.rev_prescreen_excluded,
                    ]
                    and self.settings.selected_source.replace("search/", "")
                    in r["colrev_origin"]
                ]
                if 0 == len(processed_same_toc_same_source_records):
                    print("\n\n")
                    print(toc_item)

                    for source_record_dict in sorted(
                        source_records, key=lambda d: d["author"]
                    ):
                        if all(
                            source_record_dict.get(k, "NA") == v
                            for k, v in toc_item.items()
                        ):
                            # Record(data=sr).print_citation_format()
                            print(
                                f"{source_record_dict.get('author', 'NO_AUTHOR')} : "
                                f"{source_record_dict.get('title', 'NO_TITLE')}"
                            )

                    if "y" == input(
                        "No existing records (md_processed*) found."
                        "All records unique? Set to md_processed [y]? "
                    ):
                        for source_record_dict in source_records:
                            if all(
                                source_record_dict.get(k, "NA") == v
                                for k, v in toc_item.items()
                            ):
                                source_record_dict[
                                    "colrev_status"
                                ] = colrev.record.RecordState.md_processed
                else:
                    print(toc_item)
                    print("Pre-imported records found for this toc_item (skipping)")
                    # print(processed_same_toc_same_source_records)

            for record in records.values():
                record.pop("container_title")
            dedupe_operation.review_manager.dataset.save_records_dict(records=records)
            dedupe_operation.review_manager.dataset.add_record_changes()

            if dedupe_operation.review_manager.dataset.has_changes():
                dedupe_operation.review_manager.logger.info(
                    f"{colors.GREEN}Commit changes{colors.END}"
                )
                dedupe_operation.review_manager.create_commit(
                    msg=(
                        "Merge duplicate records (set unique records from "
                        f"{self.settings.selected_source} "
                        "to md_processed)"
                    ),
                    script_call="colrev dedupe",
                    saved_args={},
                )
            else:
                dedupe_operation.review_manager.logger.info(
                    f"{colors.GREEN}No duplicates found{colors.END}"
                )

            return

        decision_list: list[dict] = []
        # decision_list =[{'ID1': ID1, 'ID2': ID2, 'decision': 'duplicate'}]

        dedupe_operation.review_manager.logger.info(
            "Identify duplicates between "
            f"curated_records and {self.settings.selected_source} (within toc_items)"
        )

        pdf_source = False
        relevant_source = [
            s
            for s in dedupe_operation.review_manager.settings.sources
            if str(s.filename) == self.settings.selected_source
        ]
        if len(relevant_source) > 0:
            pdf_source = (
                "search_pdfs_dir" == relevant_source[0].search_script["endpoint"]
            )

        if not pdf_source:
            dedupe_operation.review_manager.logger.info(
                "Processing as a non-pdf source (matching exact colrev_ids)"
            )

            # match based on overlapping  colrev_ids
            for toc_item in tqdm(toc_items):

                processed_same_toc_records = [
                    r
                    for r in records.values()
                    if all(r.get(k, "NA") == v for k, v in toc_item.items())
                    and r["colrev_status"]
                    not in [
                        colrev.record.RecordState.md_imported,
                        colrev.record.RecordState.md_needs_manual_preparation,
                        colrev.record.RecordState.md_prepared,
                        colrev.record.RecordState.rev_prescreen_excluded,
                    ]
                    and self.settings.selected_source.replace("search/", "")
                    not in r["colrev_origin"]
                ]
                new_same_toc_records = [
                    r
                    for r in source_records
                    if all(r.get(k, "NA") == v for k, v in toc_item.items())
                ]
                if len(new_same_toc_records) > 0:
                    # print(new_same_toc_records)
                    for new_same_toc_record in new_same_toc_records:
                        for rec2 in processed_same_toc_records:
                            overlapping_colrev_ids = colrev.record.Record(
                                data=new_same_toc_record
                            ).has_overlapping_colrev_id(
                                record=colrev.record.Record(data=rec2)
                            )
                            if overlapping_colrev_ids:
                                decision_list.append(
                                    {
                                        "ID1": new_same_toc_record["ID"],
                                        "ID2": rec2["ID"],
                                        "decision": "duplicate",
                                    }
                                )
                                print("TODO : validate whether it merges correctly:")
                                input(decision_list)

        else:
            dedupe_operation.review_manager.logger.info("Processing as a pdf source")

            pdf_prep_operation = (
                dedupe_operation.review_manager.get_pdf_prep_operation()
            )
            pdf_metadata_validation = (
                colrev.built_in.pdf_prep.PDFMetadataValidationEndpoint(
                    pdf_prep_operation=pdf_prep_operation,
                    settings={"name": "dedupe_pdf_md_validation"},
                )
            )

            for toc_item in tqdm(toc_items):

                processed_same_toc_records = [
                    r
                    for r in records.values()
                    if all(r.get(k, "NA") == v for k, v in toc_item.items())
                    and r["colrev_status"]
                    not in [
                        colrev.record.RecordState.md_imported,
                        colrev.record.RecordState.md_needs_manual_preparation,
                        colrev.record.RecordState.md_prepared,
                        colrev.record.RecordState.rev_prescreen_excluded,
                    ]
                    and self.settings.selected_source.replace("search/", "")
                    not in r["colrev_origin"]
                ]
                pdf_same_toc_records = [
                    r
                    for r in source_records
                    if all(r.get(k, "NA") == v for k, v in toc_item.items())
                ]

                references = pd.DataFrame.from_dict(
                    processed_same_toc_records + pdf_same_toc_records
                )

                nr_entries = references.shape[0]
                if nr_entries == 0:
                    continue
                similarity_array = np.zeros([nr_entries, nr_entries])

                # Note : min_similarity only means that the PDF will be considered
                # for validates_based_on_metadata(...), which is the acutal test!
                min_similarity = 0.7
                similarity_array, tuples_to_process = calculate_similarities(
                    similarity_array, references, min_similarity
                )

                curated_record_ids = [r["ID"] for r in processed_same_toc_records]
                pdf_record_ids = [r["ID"] for r in pdf_same_toc_records]
                for tuple_to_process in tuples_to_process:
                    rec1 = records[tuple_to_process[0]]
                    rec2 = records[tuple_to_process[1]]

                    # Note : Focus on merges between
                    # curated_records and pdf_same_toc_records
                    # Note : this should also ensure that pdf groups are not merged
                    # until a corresponding curated record group is available.
                    if (
                        rec1["ID"] in curated_record_ids
                        and rec2["ID"] in curated_record_ids
                    ):
                        continue
                    if rec1["ID"] in pdf_record_ids and rec2["ID"] in pdf_record_ids:
                        continue

                    if "file" in rec2:
                        updated_record = rec1.copy()
                        updated_record["file"] = rec2["file"]
                    elif "file" in rec1:
                        updated_record = rec2.copy()
                        updated_record["file"] = rec1["file"]
                    else:  # None of the records is curated
                        continue

                    record = colrev.record.Record(data=updated_record)
                    validation_info = (
                        pdf_metadata_validation.validates_based_on_metadata(
                            review_manager=dedupe_operation.review_manager,
                            record=record,
                        )
                    )

                    overlapping_colrev_ids = colrev.record.Record(
                        data=rec1
                    ).has_overlapping_colrev_id(record=colrev.record.Record(data=rec2))
                    if validation_info["validates"] or overlapping_colrev_ids:

                        # Note : make sure that we merge into the CURATED record
                        if "file" in rec1:
                            if tuple_to_process[0] not in [
                                x["ID1"] for x in decision_list
                            ]:
                                decision_list.append(
                                    {
                                        "ID1": tuple_to_process[0],
                                        "ID2": tuple_to_process[1],
                                        "decision": "duplicate",
                                    }
                                )
                        else:
                            if tuple_to_process[1] not in [
                                x["ID1"] for x in decision_list
                            ]:
                                decision_list.append(
                                    {
                                        "ID1": tuple_to_process[1],
                                        "ID2": tuple_to_process[0],
                                        "decision": "duplicate",
                                    }
                                )

        # Note : dedupe.apply_merges reloads the records and
        # thereby discards previous changes
        if len(decision_list) > 0:
            dedupe_operation.review_manager.logger.info(
                f"{colors.GREEN}Duplicates identified{colors.END}"
            )
            print(decision_list)
            dedupe_operation.apply_merges(results=decision_list)

            dedupe_operation.review_manager.dataset.add_record_changes()

            dedupe_operation.review_manager.create_commit(
                msg="Merge duplicate records",
                script_call="colrev dedupe",
                saved_args={},
            )
        else:
            dedupe_operation.review_manager.logger.info(
                f"{colors.GREEN}No merge-candidates identified between sets{colors.END}"
            )


@zope.interface.implementer(colrev.process.DedupeEndpoint)
class CurationMissingDedupeEndpoint:
    def __init__(self, *, dedupe_operation: colrev.dedupe.Dedupe, settings: dict):
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def run_dedupe(self, dedupe_operation: colrev.dedupe.Dedupe) -> None:

        # export sets of non-merged records
        # (and merged records a different xlsx for easy sort/merge)
        records = dedupe_operation.review_manager.dataset.load_records_dict()

        # Note : this script is necessary because the active learning is insufficient:
        # the automated ML-deduplication still has a certain error rate
        # which makes it less useful for curations
        # the active learning labeling presents cases on both sides
        # (likely duplicates and non-duplicates to maximize training quality)
        # For the curation, we are only interested in the duplicate, not the classifier

        print("\n\n")
        print(
            "In the following, "
            "records can be added to the curated (md_processed*) records.\n"
            "Curated records are displayed for the same table-of-content item "
            "(i.e., same year/volume/number)"
        )
        print("\n\n")

        nr_recs_to_merge = len(
            [
                x
                for x in records.values()
                if x["colrev_status"] in [colrev.record.RecordState.md_prepared]
            ]
        )
        nr_recs_checked = 0
        decision_list = []
        add_records_to_md_processed_list = []
        records_to_prepare = []
        for record_dict in records.values():
            if record_dict["colrev_status"] not in [
                colrev.record.RecordState.md_prepared
            ]:
                continue
            record = colrev.record.Record(data=record_dict)

            toc_key = record.get_toc_key()
            same_toc_recs = [
                r
                for r in records.values()
                if toc_key == colrev.record.Record(data=r).get_toc_key()
                if r["ID"] != record.data["ID"]
                and r["colrev_status"]
                not in [
                    colrev.record.RecordState.md_prepared,
                    colrev.record.RecordState.md_needs_manual_preparation,
                    colrev.record.RecordState.md_imported,
                ]
            ]

            if len(same_toc_recs) == 0:
                print("no same toc records")
                continue

            print("\n\n\n")
            print(colors.ORANGE)
            record.print_citation_format()
            print(colors.END)

            for same_toc_rec in same_toc_recs:
                same_toc_rec[
                    "similarity"
                ] = colrev.record.PrepRecord.get_record_similarity(
                    record_a=colrev.record.Record(data=same_toc_rec), record_b=record
                )

            same_toc_recs = sorted(
                same_toc_recs, key=lambda d: d["similarity"], reverse=True
            )

            i = 0
            for i, same_toc_rec in enumerate(same_toc_recs):
                author_title_string = (
                    f"{same_toc_rec.get('author', 'NO_AUTHOR')} : "
                    + f"{same_toc_rec.get('title', 'NO_TITLE')}"
                )

                if same_toc_rec["similarity"] > 0.8:
                    print(f"{i + 1} - {colors.ORANGE}{author_title_string}{colors.END}")

                else:
                    print(f"{i + 1} - {author_title_string}")

            valid_selection = False
            quit_pressed = False
            while not valid_selection:
                ret = input(
                    f"({nr_recs_checked}/{nr_recs_to_merge}) "
                    f"Merge with record [{1}...{i+1} / s / a / p / q]?   "
                )
                if "s" == ret:
                    valid_selection = True
                elif "q" == ret:
                    quit_pressed = True
                    valid_selection = True
                elif "a" == ret:
                    add_records_to_md_processed_list.append(record.data["ID"])
                    valid_selection = True
                elif "p" == ret:
                    records_to_prepare.append(record.data["ID"])
                    valid_selection = True
                elif ret.isdigit():
                    if int(ret) - 1 <= i:
                        decision_list.append(
                            {
                                "ID1": record.data["ID"],
                                "ID2": same_toc_recs[int(ret) - 1]["ID"],
                                "decision": "duplicate",
                            }
                        )

                        valid_selection = True
            nr_recs_checked += 1
            if quit_pressed:
                break

        if len(decision_list) > 0:
            print("Duplicates identified:")
            print(decision_list)
            dedupe_operation.apply_merges(results=decision_list)

        if len(records_to_prepare) > 0:
            records = dedupe_operation.review_manager.dataset.load_records_dict()
            for record_id, record_dict in records.items():
                if record_id in records_to_prepare:
                    record = colrev.record.Record(data=record_dict)
                    record.set_status(
                        target_state=colrev.record.RecordState.md_needs_manual_preparation
                    )

            dedupe_operation.review_manager.dataset.save_records_dict(records=records)

        if len(decision_list) > 0 or len(records_to_prepare) > 0:

            dedupe_operation.review_manager.dataset.add_record_changes()

            dedupe_operation.review_manager.create_commit(
                msg="Merge duplicate records",
                script_call="colrev dedupe",
                saved_args={},
            )

        if len(add_records_to_md_processed_list) > 0:
            records = dedupe_operation.review_manager.dataset.load_records_dict()
            for record_id, record_dict in records.items():
                if record_id in add_records_to_md_processed_list:
                    if record_dict["colrev_status"] in [
                        colrev.record.RecordState.md_prepared,
                        colrev.record.RecordState.md_needs_manual_preparation,
                        colrev.record.RecordState.md_imported,
                    ]:
                        record = colrev.record.Record(data=record_dict)
                        record.set_status(
                            target_state=colrev.record.RecordState.md_processed
                        )

            dedupe_operation.review_manager.dataset.save_records_dict(records=records)
            dedupe_operation.review_manager.dataset.add_record_changes()

            input("Edit records (if any) and press Enter")

            dedupe_operation.review_manager.dataset.add_record_changes()

            dedupe_operation.review_manager.create_commit(
                msg="Add non-duplicate records",
                script_call="colrev dedupe",
                saved_args={},
            )

        Path("dedupe").mkdir(exist_ok=True)

        source_origins = [
            str(source.filename).replace("search/", "")
            for source in dedupe_operation.review_manager.settings.sources
        ]

        # Note : reload to generate correct statistics
        records = dedupe_operation.review_manager.dataset.load_records_dict()
        for source_origin in source_origins:

            selected_records = [
                r
                for r in records.values()
                if source_origin in r["colrev_origin"]
                and r["colrev_status"]
                in [
                    colrev.record.RecordState.md_prepared,
                    colrev.record.RecordState.md_needs_manual_preparation,
                    colrev.record.RecordState.md_imported,
                ]
            ]
            records_df = pd.DataFrame.from_records(list(selected_records))
            if records_df.shape[0] == 0:
                dedupe_operation.review_manager.logger.info(
                    f"{colors.GREEN}Source {source_origin} fully merged{colors.END}"
                )
            else:
                dedupe_operation.review_manager.logger.info(
                    f"{colors.ORANGE}Source {source_origin} not fully merged{colors.END}"
                )
                dedupe_operation.review_manager.logger.info(
                    f"Exporting details to dedupe/{source_origin}.xlsx"
                )

                records_df = records_df[
                    records_df.columns.intersection(
                        {
                            "ID",
                            "colrev_status",
                            "journal",
                            "booktitle",
                            "year",
                            "volume",
                            "number",
                            "title",
                            "author",
                        }
                    )
                ]
                keys = list(
                    records_df.columns.intersection({"year", "volume", "number"})
                )
                if "year" in keys:
                    records_df.year = pd.to_numeric(records_df.year, errors="coerce")
                if "volume" in keys:
                    records_df.volume = pd.to_numeric(
                        records_df.volume, errors="coerce"
                    )
                if "number" in keys:
                    records_df.number = pd.to_numeric(
                        records_df.number, errors="coerce"
                    )
                records_df.sort_values(by=keys, inplace=True)
                records_df.to_excel(f"dedupe/{source_origin}.xlsx", index=False)
