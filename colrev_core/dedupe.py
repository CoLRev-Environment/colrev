#! /usr/bin/env python
# import json
import logging
import re
from pathlib import Path

import git
import pandas as pd

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class Dedupe(Process):

    SIMPLE_SIMILARITY_BASED_DEDUPE = "simple_similarity_based_dedupe"
    ACTIVE_LEARNING_DEDUPE = "active_learning_dedupe"
    ACTIVE_LEARNING_NON_MEMORY_DEDUPE = "active_learning_non_memory_dedupe"

    def __init__(
        self,
        *,
        REVIEW_MANAGER,
        notify_state_transition_process=True,
    ):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.dedupe,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.training_file = self.REVIEW_MANAGER.path / Path(
            ".references_dedupe_training.json"
        )
        self.settings_file = self.REVIEW_MANAGER.path / Path(
            ".references_learned_settings"
        )
        self.non_dupe_file_xlsx = self.REVIEW_MANAGER.path / Path(
            "non_duplicates_to_validate.xlsx"
        )
        self.non_dupe_file_txt = self.REVIEW_MANAGER.path / Path("dupes.txt")
        self.dupe_file = self.REVIEW_MANAGER.path / Path("duplicates_to_validate.xlsx")
        self.source_comparison_xlsx = self.REVIEW_MANAGER.path / Path(
            "source_comparison.xlsx"
        )

        self.get_dedupe_algorithm_conf()
        pd.options.mode.chained_assignment = None  # default='warn'

        self.REVIEW_MANAGER.report_logger.info("Dedupe")
        self.REVIEW_MANAGER.logger.info("Dedupe")

        self.REVIEW_MANAGER.logger.info(
            f"Selected algorithm: {self.selected_algorithm}"
        )

    def get_dedupe_algorithm_conf(
        self,
        *,
        min_n_active_learning: int = 50,
        max_n_active_learning_memory: int = 3000,
    ):

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        self.sample_size = len(record_state_list)

        self.nr_add_records = len(
            [
                r
                for r in record_state_list
                if r["colrev_status"] == RecordState.md_prepared
            ]
        )

        if self.sample_size < min_n_active_learning:
            selected_algorithm = self.SIMPLE_SIMILARITY_BASED_DEDUPE
        elif self.sample_size < max_n_active_learning_memory:
            selected_algorithm = self.ACTIVE_LEARNING_DEDUPE
        else:
            selected_algorithm = self.ACTIVE_LEARNING_NON_MEMORY_DEDUPE
        self.selected_algorithm = selected_algorithm
        return

    # Active-learning deduplication

    # Note: code based on
    # https://github.com/dedupeio/dedupe-examples/blob/master/csv_example/csv_example.py

    # - If the results list does not contain a 'score' value, it is generated
    #   manually and we cannot set the 'colrev_status' to md_processed
    # - If the results list contains a 'score value'

    def __prep_references(self, *, references: pd.DataFrame) -> dict:

        if "colrev_status" in references:
            references["colrev_status"] = references["colrev_status"].astype(str)

        if "volume" not in references:
            references["volume"] = "nan"
        if "number" not in references:
            references["number"] = "nan"
        if "pages" not in references:
            references["pages"] = "nan"
        if "year" not in references:
            references["year"] = "nan"
        else:
            references["year"] = references["year"].astype(str)
        if "author" not in references:
            references["author"] = "nan"

        references["author"] = references["author"].str[:60]

        references.loc[
            references.ENTRYTYPE == "inbook", "container_title"
        ] = references.loc[references.ENTRYTYPE == "inbook", "title"]
        if "chapter" in references:
            references.loc[references.ENTRYTYPE == "inbook", "title"] = references.loc[
                references.ENTRYTYPE == "inbook", "chapter"
            ]

        if "title" not in references:
            references["title"] = "nan"
        else:
            references["title"] = (
                references["title"]
                .str.replace(r"[^A-Za-z0-9, ]+", " ", regex=True)
                .str.lower()
            )
            references.loc[references["title"].isnull(), "title"] = "nan"

        if "journal" not in references:
            references["journal"] = ""
        else:
            references["journal"] = (
                references["journal"]
                .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
                .str.lower()
            )
        if "booktitle" not in references:
            references["booktitle"] = ""
        else:
            references["booktitle"] = (
                references["booktitle"]
                .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
                .str.lower()
            )

        if "series" not in references:
            references["series"] = ""
        else:
            references["series"] = (
                references["series"]
                .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
                .str.lower()
            )

        references["container_title"] = (
            references["journal"].fillna("")
            + references["booktitle"].fillna("")
            + references["series"].fillna("")
        )

        # To validate/improve preparation in jupyter notebook:
        # return references
        # Copy to notebook:
        # from colrev_core.review_manager import ReviewManager
        # from colrev_core import dedupe
        # from colrev_core.process import Process, ProcessType
        # REVIEW_MANAGER = ReviewManager()
        # df = dedupe.readData(REVIEW_MANAGER)
        # EDITS
        # df.to_csv('export.csv', index=False)

        references.drop(
            references.columns.difference(
                [
                    "ID",
                    "author",
                    "title",
                    "year",
                    "journal",
                    "container_title",
                    "volume",
                    "number",
                    "pages",
                    "colrev_id",
                    "colrev_origin",
                    "colrev_status",
                ]
            ),
            1,
            inplace=True,
        )
        references[
            ["author", "title", "journal", "container_title", "pages"]
        ] = references[
            ["author", "title", "journal", "container_title", "pages"]
        ].astype(
            str
        )
        references_dict = references.to_dict("records")
        self.REVIEW_MANAGER.logger.debug(
            self.REVIEW_MANAGER.pp.pformat(references_dict)
        )

        data_d = {}

        for row in references_dict:
            # Note: we need the ID to identify/remove duplicates in the MAIN_REFERENCES.
            # It is ignored in the field-definitions by the deduper!
            # clean_row = [(k, preProcess(k, v)) for (k, v) in row.items() if k != "ID"]
            clean_row = [
                (k, self.__preProcess(k=k, column=v)) for (k, v) in row.items()
            ]
            data_d[row["ID"]] = dict(clean_row)

        return data_d

    def __preProcess(self, *, k, column):
        """
        Do a little bit of data cleaning with the help of Unidecode and Regex.
        Things like casing, extra spaces, quotes and new lines can be ignored.
        """
        if k in ["ID", "ENTRYTYPE", "colrev_status", "colrev_origin"]:
            return column

        column = str(column)
        if any(
            column == x
            for x in ["no issue", "no volume", "no pages", "no author", "nan"]
        ):
            column = None
            return column

        # Note unidecode may be an alternative to rmdiacritics/remove_accents.
        # It would be important to operate on a per-character basis
        # instead of throwing an exception when processing whole strings
        # column = unidecode(column)
        column = re.sub("  +", " ", column)
        column = re.sub("\n", " ", column)
        column = column.strip().strip('"').strip("'").lower().strip()
        # If data is missing, indicate that by setting the value to `None`
        if not column:
            column = None
        return column

    def __readData(self):
        from colrev_core.record import Record, NotEnoughDataToIdentifyException

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        # Note: Because we only introduce individual (non-merged records),
        # there should be no semicolons in colrev_origin!
        records_queue = [
            x
            for x in records.values()
            if x["colrev_status"]
            not in [RecordState.md_imported, RecordState.md_needs_manual_preparation]
        ]

        # Do not merge records with non_latin_alphabets:
        records_queue = [
            x
            for x in records_queue
            if not (
                RecordState.rev_prescreen_excluded == x["colrev_status"]
                and "script:non_latin_alphabet" == x.get("prescreen_exclusion", "")
            )
        ]

        for r in records_queue:
            try:
                RECORD = Record(data=r)
                r["colrev_id"] = RECORD.create_colrev_id()
            except NotEnoughDataToIdentifyException:
                r["colrev_id"] = "NA"
                pass

        references = pd.DataFrame.from_dict(records_queue)
        references = self.__prep_references(references=references)

        return references

    def setup_active_learning_dedupe(self, *, retrain: bool, in_memory: bool):
        """Prepare data for active learning setup"""
        import dedupe
        import random

        logging.getLogger("opensearch").setLevel(logging.ERROR)
        logging.getLogger("dedupe.training").setLevel(logging.WARNING)
        logging.getLogger("dedupe.api").setLevel(logging.WARNING)
        # logging.getLogger("rlr.crossvalidation:optimum").setLevel(logging.WARNING)

        if retrain:
            # Note : removing the training_file would be to start from scratch...
            # self.training_file.unlink(missing_ok=True)
            self.settings_file.unlink(missing_ok=True)

        self.REVIEW_MANAGER.logger.info("Importing data ...")

        # Possible extension: in the readData, we may want to append the colrev_status
        # to use Gazetteer (dedupe_io) if applicable (no duplicates in pos-md_processed)

        data_d = self.__readData()

        # to address memory issues, we select a sample from data_d
        # and feed it to prepare_training:
        # https://github.com/dedupeio/dedupe/issues/920

        if not in_memory:
            # Note: we have to make sure that when we sample for training,
            # the not-in-memory mode is used for duplicate clustering
            # otherwise, non-sampled duplicates will not be identified
            max_training_sample_size = min(3000, len(list(data_d.keys())))
            self.REVIEW_MANAGER.logger.info(
                f"Selecting a random sample of {max_training_sample_size}"
                " to avoid memory problems"
            )
            # TODO : consider similar proportions of post-md_processed/md_prepared?
            keys = random.sample(list(data_d.keys()), max_training_sample_size)
            data_d = {key: data_d[key] for key in keys}

        self.n_new = len(
            [d for d, v in data_d.items() if "md_prepared" == v["colrev_status"]]
        )

        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(data_d))

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
        deduper = dedupe.Dedupe(fields)

        # If we have training data saved from a previous run of dedupe,
        # look for it and load it in.
        # __Note:__ if you want to train from scratch, delete the training_file
        if self.training_file.is_file():
            self.REVIEW_MANAGER.logger.info(
                f"Reading pre-labeled training data from {self.training_file.name} "
                "and preparing data"
            )
            with open(self.training_file, "rb") as f:
                deduper.prepare_training(data_d, f)
        else:
            deduper.prepare_training(data_d)

        # TODO  input('del data_d - check memory')
        del data_d

        self.REVIEW_MANAGER.logger.info("Reading and preparation completed.")

        self.deduper = deduper

        return

    def select_primary_merge_record(self, rec_ID1, rec_ID2) -> list:
        from colrev_core.record import Record

        # Heuristic

        # 1. if both records are prepared (or the same status),
        # merge into the record with the lower colrev_id
        if rec_ID1["colrev_status"] == rec_ID2["colrev_status"]:
            if rec_ID1["ID"][-1].isdigit() and not rec_ID2["ID"][-1].isdigit():
                main_record = rec_ID1
                dupe_record = rec_ID2
            # TODO : elif: check which of the appended letters is first in the alphabet
            else:
                main_record = rec_ID2
                dupe_record = rec_ID1

        # 2. If a record is md_prepared, use it as the dupe record
        elif rec_ID1["colrev_status"] == RecordState.md_prepared:
            main_record = rec_ID2
            dupe_record = rec_ID1
        elif rec_ID2["colrev_status"] == RecordState.md_prepared:
            main_record = rec_ID1
            dupe_record = rec_ID2

        # 3. If a record is md_processed, use it as the dupe record
        # -> during the fix_errors procedure, records are in md_processed
        # and beyond.
        elif rec_ID1["colrev_status"] == RecordState.md_processed:
            main_record = rec_ID2
            dupe_record = rec_ID1
        elif rec_ID2["colrev_status"] == RecordState.md_processed:
            main_record = rec_ID1
            dupe_record = rec_ID2

        # 4. Merge into curated record (otherwise)
        else:
            if Record(data=rec_ID2).masterdata_is_curated():
                main_record = rec_ID2
                dupe_record = rec_ID1
            else:
                main_record = rec_ID1
                dupe_record = rec_ID2
        return [main_record, dupe_record]

    def apply_merges(self, *, results: list, remaining_non_dupe: bool = False):
        """Apply automated deduplication decisions

        Level: IDs (not colrev_origins), requiring IDs to be immutable after md_prepared

        record['colrev_status'] can only be set to md_processed after running the
        active-learning classifier and checking whether the record is not part of
        any other duplicate-cluster
        - If the results list does not contain a 'score' value, it is generated
        manually and we cannot set the 'colrev_status' to md_processed
        - If the results list contains a 'score value'

        """
        from colrev_core.record import Record

        # The merging also needs to consider whether IDs are propagated
        # Completeness of comparisons should be ensured by the
        # dedupe clustering routine

        class colors:
            RED = "\033[91m"
            GREEN = "\033[92m"
            ORANGE = "\033[93m"
            BLUE = "\033[94m"
            END = "\033[0m"

        def same_source_merge(main_record: dict, dupe_record: dict) -> bool:

            main_rec_sources = [
                x.split("/")[0] for x in main_record["colrev_origin"].split(";")
            ]
            dupe_rec_sources = [
                x.split("/")[0] for x in dupe_record["colrev_origin"].split(";")
            ]
            same_sources = set(main_rec_sources).intersection(set(dupe_rec_sources))
            if len(same_sources) > 0:
                return True

            return False

        def export_same_source_merge(main_record: dict, dupe_record: dict) -> None:

            merge_info = main_record["ID"] + "," + dupe_record["ID"]
            same_source_merge_file = Path("same_source_merges.txt")
            with same_source_merge_file.open("a", encoding="utf8") as f:
                f.write(merge_info + "\n")
            self.REVIEW_MANAGER.logger.warning(
                f"Prevented same-source merge: ({merge_info})"
            )

            return

        def cross_level_merge(main_record, dupe_record) -> bool:
            cross_level_merge_attempt = False
            if main_record["ENTRYTYPE"] in ["proceedings"] or dupe_record[
                "ENTRYTYPE"
            ] in ["proceedings"]:
                cross_level_merge_attempt = True
            # TODO: book vs. inbook?
            return cross_level_merge_attempt

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for non_dupe in [x["ID1"] for x in results if "no_duplicate" == x["decision"]]:
            if non_dupe in records:
                records[non_dupe].update(colrev_status=RecordState.md_processed)

        removed_duplicates = []
        for dupe in [x for x in results if "duplicate" == x["decision"]]:

            rec_ID1 = records[dupe["ID1"]]
            rec_ID2 = records[dupe["ID2"]]

            # Simple way of implementing the closure
            # cases where the main_record has already been merged into another record
            while "MOVED_DUPE" in rec_ID1:
                rec_ID1 = records[rec_ID1["MOVED_DUPE"]]
            while "MOVED_DUPE" in rec_ID2:
                rec_ID2 = records[rec_ID2["MOVED_DUPE"]]

            main_record, dupe_record = self.select_primary_merge_record(
                rec_ID1, rec_ID2
            )

            if cross_level_merge(main_record, dupe_record):
                continue

            if same_source_merge(main_record, dupe_record):
                if "apply" != self.REVIEW_MANAGER.settings.dedupe.same_source_merges:
                    print(
                        f"\n{colors.ORANGE}"
                        "Warning: applying same source merge "
                        f"{colors.END} "
                        f"{main_record.get('colrev_origin', '')}/"
                        f"{dupe_record.get('colrev_origin', '')}\n"
                        f"  {Record(data=main_record).format_bib_style()}\n"
                        f"  {Record(data=dupe_record).format_bib_style()}"
                    )
                elif (
                    "prevent" == self.REVIEW_MANAGER.settings.dedupe.same_source_merges
                ):
                    export_same_source_merge(main_record, dupe_record)
                    continue  # with next pair
                else:
                    print(
                        "Invalid setting: dedupe.same_source_merges: "
                        f"{self.REVIEW_MANAGER.settings.dedupe.same_source_merges}"
                    )
                    continue  # with next pair

            dupe_record["MOVED_DUPE"] = main_record["ID"]
            MAIN_RECORD = Record(data=main_record)
            MAIN_RECORD.merge(
                MERGING_RECORD=Record(data=dupe_record), default_source="merged"
            )
            main_record = MAIN_RECORD.get_data()

            if "score" in dupe:
                conf_details = f"(confidence: {str(round(dupe['score'], 3))})"
            else:
                conf_details = ""
            self.REVIEW_MANAGER.logger.debug(
                f"Removed duplicate{conf_details}: "
                + f'{main_record["ID"]} <- {dupe_record["ID"]}'
            )

            removed_duplicates.append(dupe_record["ID"])

        for record in records.values():
            if "MOVED_DUPE" in record:
                del record["MOVED_DUPE"]
        for removed_duplicate in removed_duplicates:
            if removed_duplicate in records:
                del records[removed_duplicate]

        if remaining_non_dupe:
            # Set remaining records to md_processed (not duplicate) because all records
            # have been considered by dedupe
            for record in records.values():
                if record["colrev_status"] == RecordState.md_prepared:
                    record["colrev_status"] = RecordState.md_processed

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def apply_manual_deduplication_decisions(self, *, results: list):
        """Apply manual deduplication decisions

        Level: IDs (not colrev_origins), requiring IDs to be immutable after md_prepared

        Note : record['colrev_status'] can only be set to md_processed after running the
        active-learning classifier and checking whether the record is not part of
        any other duplicate-cluster
        """
        from colrev_core.record import Record

        # The merging also needs to consider whether IDs are propagated

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        non_dupe_list = []
        dupe_list = []
        for x in results:
            if "no_duplicate" == x["decision"]:
                non_dupe_list.append([x["ID1"], x["ID2"]])
            if "duplicate" == x["decision"]:
                dupe_list.append([x["ID1"], x["ID2"]])

        removed_duplicates = []
        for ID1, ID2 in dupe_list:

            rec_ID1 = records[ID1]
            rec_ID2 = records[ID2]

            self.REVIEW_MANAGER.logger.debug(
                f'applying {rec_ID1["ID"]}-{rec_ID2["ID"]}'
            )

            # Simple way of implementing the closure
            # cases where the main_record has already been merged into another record
            while "MOVED_DUPE" in rec_ID1:
                rec_ID1 = records[rec_ID1["MOVED_DUPE"]]
            while "MOVED_DUPE" in rec_ID2:
                rec_ID2 = records[rec_ID2["MOVED_DUPE"]]

            if rec_ID1["ID"] == rec_ID2["ID"]:
                continue

            main_record, dupe_record = self.select_primary_merge_record(
                rec_ID1, rec_ID2
            )

            # TODO : prevent same-source merges (like in the automated part?!)
            dupe_rec_id = dupe_record["ID"]
            main_rec_id = main_record["ID"]
            self.REVIEW_MANAGER.logger.debug(main_rec_id + " < " + dupe_rec_id)

            dupe_record["MOVED_DUPE"] = main_record["ID"]
            MAIN_RECORD = Record(data=main_record)
            MAIN_RECORD.merge(
                MERGING_RECORD=Record(data=dupe_record), default_source="merged"
            )
            main_record = MAIN_RECORD.get_data()

            self.REVIEW_MANAGER.logger.debug(
                f"Removed duplicate: {dupe_rec_id} (duplicate of {main_rec_id})"
            )
            removed_duplicates.append(dupe_rec_id)

        for record in records.values():
            if "MOVED_DUPE" in record:
                del record["MOVED_DUPE"]
        for removed_duplicate in removed_duplicates:
            if removed_duplicate in records:
                del records[removed_duplicate]

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def source_comparison(self) -> None:
        """Exports a spreadsheet to support analyses of records that are not
        in all sources (for curated repositories)"""

        source_details = self.REVIEW_MANAGER.REVIEW_DATASET.load_sources()
        source_filenames = [x.filename for x in source_details]
        print("sources: " + ",".join(source_filenames))

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        records = {
            k: v
            for k, v in records.items()
            if not all(x in v["colrev_origin"] for x in source_filenames)
        }
        if len(records) == 0:
            print("No records unmatched")
            return

        for record in records.values():
            origins = record["colrev_origin"].split(";")
            for source_filename in source_filenames:
                if not any(source_filename in origin for origin in origins):
                    record[source_filename] = ""
                else:
                    record[source_filename] = [
                        origin for origin in origins if source_filename in origin
                    ][0]
            record["merge_with"] = ""

        records_df = pd.DataFrame.from_records(list(records.values()))
        records_df.to_excel(self.source_comparison_xlsx, index=False)
        print(f"Exported {self.source_comparison_xlsx}")
        return

    def fix_errors(self) -> None:
        """Fix errors as highlighted in the Excel files"""

        self.REVIEW_MANAGER.report_logger.info("Dedupe: fix errors")
        self.REVIEW_MANAGER.logger.info("Dedupe: fix errors")
        saved_args = locals()

        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        if self.dupe_file.is_file():
            dupes = pd.read_excel(self.dupe_file)
            dupes.fillna("", inplace=True)
            c_to_correct = dupes.loc[dupes["error"] != "", "cluster_id"].to_list()
            dupes = dupes[dupes["cluster_id"].isin(c_to_correct)]
            IDs_to_unmerge = dupes.groupby(["cluster_id"])["ID"].apply(list).tolist()

            if len(IDs_to_unmerge) > 0:
                records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

                MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths[
                    "MAIN_REFERENCES_RELATIVE"
                ]
                revlist = (
                    ((commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read())
                    for commit in git_repo.iter_commits(
                        paths=str(MAIN_REFERENCES_RELATIVE)
                    )
                )

                # Note : there could be more than two IDs in the list
                filecontents = next(revlist)

                prior_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records(
                    load_str=filecontents.decode("utf-8")
                )

                for ID_list_to_unmerge in IDs_to_unmerge:
                    self.REVIEW_MANAGER.report_logger.info(
                        f'Undo merge: {",".join(ID_list_to_unmerge)}'
                    )

                    # delete new record,
                    # add previous records (from history) to records
                    records = {
                        k: v for k, v in records.items() if k not in ID_list_to_unmerge
                    }

                    if all([ID in prior_records_dict for ID in ID_list_to_unmerge]):
                        for r in prior_records_dict.values():
                            if r["ID"] in ID_list_to_unmerge:
                                # add manual_dedupe/non_dupe decision to the records
                                manual_non_duplicates = ID_list_to_unmerge.copy()
                                manual_non_duplicates.remove(r["ID"])

                                r["colrev_status"] = RecordState.md_processed
                                r_dict = {r["ID"]: r}
                                records.append(r_dict)
                                self.REVIEW_MANAGER.logger.info(f'Restored {r["ID"]}')
                    else:
                        self.REVIEW_MANAGER.logger.error(
                            f"Could not retore {ID_list_to_unmerge} - "
                            "please fix manually"
                        )

                self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
                self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        if self.non_dupe_file_xlsx.is_file() or self.non_dupe_file_txt.is_file():
            IDs_to_merge = []
            if self.non_dupe_file_xlsx.is_file():
                non_dupes = pd.read_excel(self.non_dupe_file_xlsx)
                non_dupes.fillna("", inplace=True)
                c_to_correct = non_dupes.loc[
                    non_dupes["error"] != "", "cluster_id"
                ].to_list()
                non_dupes = non_dupes[non_dupes["cluster_id"].isin(c_to_correct)]
                IDs_to_merge = (
                    non_dupes.groupby(["cluster_id"])["ID"].apply(list).tolist()
                )
            if self.non_dupe_file_txt.is_file():
                content = self.non_dupe_file_txt.read_text()
                IDs_to_merge = [x.split(",") for x in content.splitlines()]
                for ID1, ID2 in IDs_to_merge:
                    print(f"{ID1} - {ID2}")

            if len(IDs_to_merge) > 0:
                auto_dedupe = []
                for ID1, ID2 in IDs_to_merge:
                    auto_dedupe.append(
                        {
                            "ID1": ID1,
                            "ID2": ID2,
                            "decision": "duplicate",
                        }
                    )
                self.apply_manual_deduplication_decisions(results=auto_dedupe)

        if (
            self.dupe_file.is_file()
            or self.non_dupe_file_xlsx.is_file()
            or self.non_dupe_file_txt.is_file()
        ):
            self.REVIEW_MANAGER.create_commit(
                msg="Validate and correct duplicates",
                manual_author=True,
                saved_args=saved_args,
            )
        else:
            self.REVIEW_MANAGER.logger.error("No file with potential errors found.")
        return

    def apply_active_learning(self, results, saved_args):

        self.apply_manual_deduplication_decisions(results=results)

        # Using the examples we just labeled, train the deduper and learn
        # blocking predicates
        self.deduper.train(recall=0.9, index_predicates=True)
        # print(deduper.data_model._field_comparators)
        # print(deduper.predicates)

        # When finished, save our training to disk
        with open(self.training_file, "w") as tf:
            self.deduper.write_training(tf)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path=self.training_file)

        # Save our weights and predicates to disk.  If the settings file
        # exists, we will skip all the training and learning next time we run
        # this file.
        with open(self.settings_file, "wb") as sf:
            self.deduper.write_settings(sf)

        self.REVIEW_MANAGER.create_commit(
            msg="Labeling of duplicates (active learning)",
            manual_author=True,
            saved_args=saved_args,
        )
        # deduper.cleanup_training()

        return

    def cluster_tuples(
        self,
        *,
        partition_threshold: float = None,
        merge_threshold: float = None,
        in_memory: bool = True,
        saved_args: dict,
    ):
        """Cluster potential duplicates, merge, and export validation spreadsheets"""

        import statistics
        import dedupe
        import sqlite3

        with open(self.settings_file, "rb") as sf:
            deduper = dedupe.StaticDedupe(sf, num_cores=4)

        self.REVIEW_MANAGER.logger.info("Clustering duplicates...")

        data_d = self.__readData()
        self.REVIEW_MANAGER.logger.info(
            f"Number of records (before): {len(data_d.items())}"
        )

        # `partition` will return sets of records that dedupe
        # believes are all referring to the same entity.

        if merge_threshold is None:
            merge_threshold = self.REVIEW_MANAGER.settings.dedupe.merge_threshold

        if partition_threshold is None:
            partition_threshold = (
                self.REVIEW_MANAGER.settings.dedupe.partition_threshold
            )

        saved_args.update(merge_threshold=str(merge_threshold))
        saved_args.update(partition_threshold=str(partition_threshold))

        if in_memory:
            self.REVIEW_MANAGER.report_logger.info(
                f"set partition_threshold: {partition_threshold}"
            )

            clustered_dupes = deduper.partition(data_d, partition_threshold)

        else:

            for field in deduper.fingerprinter.index_fields:
                field_data = (r[field] for r in data_d.values() if field in r)
                deduper.fingerprinter.index(field_data, field)

            full_data = ((r["ID"], r) for r in data_d.values())
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

                for i, row in enumerate(result_set):
                    ID_a, ID_b = row
                    record_a = (ID_a, records_data[ID_a])
                    record_b = (ID_b, records_data[ID_b])

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

        self.REVIEW_MANAGER.report_logger.info(
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
        ID_list = []
        self.REVIEW_MANAGER.report_logger.info(
            f"set merge_threshold: {merge_threshold}"
        )
        self.REVIEW_MANAGER.logger.info(f"set merge_threshold: {merge_threshold}")
        for dedupe_decision in dedupe_decision_list:

            if len(dedupe_decision["records"]) > 1:
                if dedupe_decision["score"] > merge_threshold:
                    orig_rec = dedupe_decision["records"].pop()
                    ID_list.append(orig_rec)
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
                            self.REVIEW_MANAGER.REVIEW_DATASET.propagated_ID(
                                ID=orig_rec
                            )
                        )
                        dupe_propagated = (
                            self.REVIEW_MANAGER.REVIEW_DATASET.propagated_ID(
                                ID=dupe_rec
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
                                self.REVIEW_MANAGER.logger.error(
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

        self.apply_merges(results=auto_dedupe, remaining_non_dupe=True)

        self.REVIEW_MANAGER.reorder_log(IDs=ID_list, criterion="descending_thresholds")

        # Export excels for validation
        def highlight_cells(x):
            df = x.copy()
            df["cluster_id"] = df["cluster_id"].astype(str)
            df.loc[:, df.columns != "cluster_id"] = "background-color: white"

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

            prev_row = []
            for i, row in df.iterrows():
                if row["cluster_id"] != cur_cluster:
                    cur_color_index += 1
                    cur_cluster = row["cluster_id"]
                # df.at[i, 'cluster_id'] = ( # only the cluster_id column
                df.at[i, :] = (
                    "background-color: "
                    + available_colors[cur_color_index % len(available_colors)]
                )

            for i, row in x.iterrows():
                if i == 0 or i == 1:
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
                            df.at[i, j] = df.at[i, j] + "; font-weight: bold"

                prev_row = row

            return df

        collected_duplicates = []
        collected_non_duplicates = []
        for ID, vals in data_d.items():
            vals.update(error="")
            if ID in cluster_membership:
                cur_cluster_membership = cluster_membership[ID]
                vals.update(cur_cluster_membership)
                if cur_cluster_membership["confidence_score"] > merge_threshold:
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
            duplicates_df.to_excel(self.dupe_file, index=False)

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
                non_duplicates_df.to_excel(self.non_dupe_file_xlsx, index=False)

        class colors:
            RED = "\033[91m"
            GREEN = "\033[92m"
            ORANGE = "\033[93m"
            BLUE = "\033[94m"
            END = "\033[0m"

        self.REVIEW_MANAGER.create_commit(
            msg="Deduplication (based on active-learning clusters)",
            saved_args=saved_args,
        )

        self.REVIEW_MANAGER.logger.info(
            "Successfully completed the deduplication. Please check the "
            "duplicates_to_validate.xlsx and non_duplicates_to_validate.xlsx for "
            'potential errors.\nTo fix them, mark them in the "error" column and '
            "run\n  colrev dedupe --fix_errors\n\n"
        )

        if Path("same_source_merges.txt").is_file():
            self.REVIEW_MANAGER.logger.info(
                "Detected and prevented same-source merges. Please check potential"
                "duplicates in same_source_merges.txt"
            )

        info = self.get_info()
        if len(info["same_source_merges"]) > 0:
            self.REVIEW_MANAGER.logger.info(
                f"\n{colors.ORANGE}Same source merges to check:{colors.END}"
                "\n- ".join(info["same_source_merges"]) + "\n"
            )
        else:
            self.REVIEW_MANAGER.logger.info("\nNo same-origin merges detected.")

        return

    def get_info(self) -> dict:
        """Get info on cuts (overlap of search sources) and same source merges"""
        import itertools
        from collections import Counter

        def __get_toc_key(record: dict) -> str:
            toc_key = "NA"
            if "article" == record["ENTRYTYPE"]:
                toc_key = f"{record.get('journal', '').lower()}"
                if "year" in record:
                    toc_key = toc_key + f"|{record['year']}"
                if "volume" in record:
                    toc_key = toc_key + f"|{record['volume']}"
                if "number" in record:
                    toc_key = toc_key + f"|{record['number']}"
                else:
                    toc_key = toc_key + "|"
            elif "inproceedings" == record["ENTRYTYPE"]:
                toc_key = (
                    f"{record.get('booktitle', '').lower()}"
                    + f"|{record.get('year', '')}"
                )

            return toc_key

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        origins = [record["colrev_origin"].split(";") for record in records.values()]
        origins = [item.split("/")[0] for sublist in origins for item in sublist]
        origins = list(set(origins))

        cuts = {}
        same_source_merges = []
        for L in range(1, len(origins) + 1):
            for subset in itertools.combinations(origins, L):
                cuts["/".join(list(subset))] = {
                    "colrev_origins": list(subset),
                    "records": [],
                }

        for record in records.values():

            rec_sources = [x.split("/")[0] for x in record["colrev_origin"].split(";")]

            duplicated_sources = [
                item for item, count in Counter(rec_sources).items() if count > 1
            ]
            if len(duplicated_sources) > 0:
                all_cases = []
                for ds in duplicated_sources:
                    cases = [
                        o.split("/")[1]
                        for o in record["colrev_origin"].split(";")
                        if ds in o
                    ]
                    all_cases.append(f"{ds}: {cases}")
                same_source_merges.append(f"{record['ID']} ({', '.join(all_cases)})")

            cut_list = [
                x
                for k, x in cuts.items()
                if set(x["colrev_origins"]) == set(rec_sources)
            ]
            if len(cut_list) != 1:
                print(cut_list)
                print(record["ID"], record["colrev_origin"])
                continue
            cut = cut_list[0]
            cut["records"].append(record["ID"])

            if "toc_items" not in cut:
                cut["toc_items"] = {}  # type: ignore
            toc_i = __get_toc_key(record)
            if toc_i in cut["toc_items"]:
                cut["toc_items"][toc_i] = cut["toc_items"][toc_i] + 1  # type: ignore
            else:
                cut["toc_items"][toc_i] = 1  # type: ignore

        total = len(records.values())
        for k, det in cuts.items():
            det["size"] = len(det["records"])  # type: ignore
            det["fraction"] = det["size"] / total * 100  # type: ignore

        info = {"cuts": cuts, "same_source_merges": same_source_merges}
        return info

    # -------------  SIMPLE MERGING PROCEDURES FOR SMALL SAMPLES  ------------------

    def __calculate_similarities_record(self, *, references: pd.DataFrame) -> list:
        from colrev_core.record import Record

        # Note: per definition, similarities are needed relative to the last row.
        references["similarity"] = 0
        references["details"] = 0
        sim_col = references.columns.get_loc("similarity")
        details_col = references.columns.get_loc("details")
        for base_record_i in range(0, references.shape[0]):
            sim_details = Record.get_similarity_detailed(
                df_a=references.iloc[base_record_i], df_b=references.iloc[-1]
            )
            self.REVIEW_MANAGER.report_logger.debug(
                f"Similarity score: {sim_details['score']}"
            )
            self.REVIEW_MANAGER.report_logger.debug(sim_details["details"])

            references.iloc[base_record_i, sim_col] = sim_details["score"]
            references.iloc[base_record_i, details_col] = sim_details["details"]
        # Note: return all other records (not the comparison record/first row)
        # and restrict it to the ID, similarity and details
        ck_col = references.columns.get_loc("ID")
        sim_col = references.columns.get_loc("similarity")
        details_col = references.columns.get_loc("details")
        return references.iloc[:, [ck_col, sim_col, details_col]]

    def __append_merges(self, *, batch_item: dict) -> dict:

        self.REVIEW_MANAGER.logger.debug(f'append_merges {batch_item["record"]}')

        references = batch_item["queue"]

        # if the record is the first one added to the records
        # (in a preceding processing step), it can be propagated
        # if len(batch_item["queue"]) < 2:
        if len(references.index) < 2:
            return {
                "ID1": batch_item["record"],
                "ID2": "NA",
                "similarity": 1,
                "decision": "no_duplicate",
            }

        # df to get_similarities for each other record
        references = self.__calculate_similarities_record(references=references)
        # drop the first row (similarities are calculated relative to the last row)
        references = references.iloc[:-1, :]
        # if batch_item['record'] == 'AdamsNelsonTodd1992':
        #     references.to_csv('last_similarities.csv')

        max_similarity = references.similarity.max()

        # TODO: it may not be sufficient to consider
        # the record with the highest similarity

        if max_similarity <= batch_item["MERGING_NON_DUP_THRESHOLD"]:
            # Note: if no other record has a similarity exceeding the threshold,
            # it is considered a non-duplicate (in relation to all other records)
            self.REVIEW_MANAGER.logger.debug(f"max_similarity ({max_similarity})")
            return {
                "ID1": batch_item["record"],
                "ID2": "NA",
                "similarity": max_similarity,
                "decision": "no_duplicate",
            }

        elif (
            max_similarity > batch_item["MERGING_NON_DUP_THRESHOLD"]
            and max_similarity < batch_item["MERGING_DUP_THRESHOLD"]
        ):

            ID = references.loc[references["similarity"].idxmax()]["ID"]
            self.REVIEW_MANAGER.logger.debug(
                f"max_similarity ({max_similarity}): {batch_item['record']} {ID}"
            )
            details = references.loc[references["similarity"].idxmax()]["details"]
            self.REVIEW_MANAGER.logger.debug(details)
            # record_a, record_b = sorted([ID, record["ID"]])
            msg = (
                f'{batch_item["record"]} - {ID}'.ljust(35, " ")
                + f"  - potential duplicate (similarity: {max_similarity})"
            )
            self.REVIEW_MANAGER.report_logger.info(msg)
            self.REVIEW_MANAGER.logger.info(msg)
            return {
                "ID1": batch_item["record"],
                "ID2": ID,
                "similarity": max_similarity,
                "decision": "potential_duplicate",
            }

        else:  # max_similarity >= batch_item["MERGING_DUP_THRESHOLD"]:
            # note: the following status will not be saved in the bib file but
            # in the duplicate_tuples.csv (which will be applied to the bib file
            # in the end)
            ID = references.loc[references["similarity"].idxmax()]["ID"]
            self.REVIEW_MANAGER.logger.debug(
                f"max_similarity ({max_similarity}): {batch_item['record']} {ID}"
            )
            details = references.loc[references["similarity"].idxmax()]["details"]
            self.REVIEW_MANAGER.logger.debug(details)
            msg = (
                f'Dropped duplicate: {batch_item["record"]} (duplicate of {ID})'
                + f" (similarity: {max_similarity})\nDetails: {details}"
            )
            self.REVIEW_MANAGER.report_logger.info(msg)
            self.REVIEW_MANAGER.logger.info(msg)
            return {
                "ID1": batch_item["record"],
                "ID2": ID,
                "similarity": max_similarity,
                "decision": "duplicate",
            }

    def __batch(self, *, data):
        # the queue (order) matters for the incremental merging (make sure that each
        # additional record is compared to/merged with all prior records in
        # the queue)

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        # Note: Because we only introduce individual (non-merged records),
        # there should be no semicolons in colrev_origin!
        records_queue = [
            record for ID, record in records.items() if ID in data["queue"]
        ]

        records_queue = pd.DataFrame.from_dict(records_queue)
        references = self.__prep_references(references=records_queue)
        # self.REVIEW_MANAGER.pp.pprint(references.values())
        references = pd.DataFrame(references.values())

        # TODO : simplify this function (e.g., batch size n no longer needed)
        n = 100
        items_start = data["items_start"]
        it_len = len(data["queue"])
        batch_data = []
        for ndx in range(items_start // n, it_len, n):
            for i in range(ndx, min(ndx + n, it_len)):
                batch_data.append(
                    {
                        "record": data["queue"][i],
                        "queue": references.iloc[: i + 1],
                        "MERGING_NON_DUP_THRESHOLD": 0.7,
                        "MERGING_DUP_THRESHOLD": 0.95,
                    }
                )

        for ndx in range(0, it_len, n):
            yield batch_data[ndx : min(ndx + n, it_len)]

    def __get_data(self):

        # Note: this would also be a place to set
        # records as "no-duplicate" by definition
        # (e.g., for non-duplicated sources marked in the sources)

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        IDs_to_dedupe = [
            x["ID"]
            for x in record_state_list
            if x["colrev_status"] == str(RecordState.md_prepared)
        ]
        processed_IDs = [
            x["ID"]
            for x in record_state_list
            if x["colrev_status"]
            not in [
                str(RecordState.md_imported),
                str(RecordState.md_prepared),
                str(RecordState.md_needs_manual_preparation),
            ]
        ]

        nr_tasks = len(IDs_to_dedupe)
        dedupe_data = {
            "nr_tasks": nr_tasks,
            "queue": processed_IDs + IDs_to_dedupe,
            "items_start": len(processed_IDs),
        }
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(dedupe_data))

        return dedupe_data

    def simple_dedupe(self) -> None:
        """Pairwise identification of duplicates based on static similarity measure

        This procedure should only be used in small samples on which active learning
        models cannot be trained.
        """

        saved_args = locals()

        self.REVIEW_MANAGER.logger.info(
            "Pairwise identification of duplicates based on static similarity measure"
        )

        dedupe_data = self.__get_data()

        i = 1
        for dedupe_batch in self.__batch(data=dedupe_data):

            # print(f"Batch {i}")
            i += 1
            dedupe_batch_results = []
            for item in dedupe_batch:
                dedupe_batch_results.append(self.__append_merges(batch_item=item))

            # dedupe_batch[-1]['queue'].to_csv('last_references.csv')

            self.apply_merges(results=dedupe_batch_results)

            self.potential_duplicates = [
                r
                for r in dedupe_batch_results
                if "potential_duplicate" == r["decision"]
            ]

            records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

            records_queue = pd.DataFrame.from_dict(records.values())
            references = self.__prep_references(references=records_queue)
            # self.REVIEW_MANAGER.pp.pprint(references.values())
            references = pd.DataFrame(references.values())

            self.dedupe_references = references

            self.REVIEW_MANAGER.create_commit(
                msg="Process duplicates", saved_args=saved_args
            )

        if 1 == i:
            self.REVIEW_MANAGER.logger.info("No records to check for duplicates")

        return


if __name__ == "__main__":
    pass
