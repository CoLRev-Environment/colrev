#! /usr/bin/env python
# import json
import logging
import re
from pathlib import Path

import git
import pandas as pd

from colrev_core import utils
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class Dedupe(Process):

    md_keys = [
        "author",
        "title",
        "year",
        "journal",
        "booktitle",
        "volume",
        "number",
        "pages",
    ]
    complementary_keys = ["doi", "url", "abstract", "dblk_key"]

    def __init__(self, REVIEW_MANAGER, notify_state_transition_process=True):

        super().__init__(
            REVIEW_MANAGER,
            ProcessType.dedupe,
            notify_state_transition_process=notify_state_transition_process,
        )

        pd.options.mode.chained_assignment = None  # default='warn'

    # Active-learning deduplication

    # Note: code based on
    # https://github.com/dedupeio/dedupe-examples/blob/master/csv_example/csv_example.py

    # - If the results list does not contain a 'score' value, it is generated
    #   manually and we cannot set the 'status' to md_processed
    # - If the results list contains a 'score value'

    # IMPORTANT: manual_duplicate/manual_non_duplicate fields:
    # ID in the (same) deduplication commit
    # the same ID may be used for other records in following commits!

    def __prep_references(self, references: pd.DataFrame) -> dict:

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
        else:
            references["author"] = references["author"].apply(
                lambda x: utils.format_authors_string(x)
            )
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
                    "colrev_ID",
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
            clean_row = [(k, self.__preProcess(k, v)) for (k, v) in row.items()]
            data_d[row["ID"]] = dict(clean_row)

        return data_d

    def __preProcess(self, k, column):
        """
        Do a little bit of data cleaning with the help of Unidecode and Regex.
        Things like casing, extra spaces, quotes and new lines can be ignored.
        """
        if k in ["ID", "ENTRYTYPE", "status"]:
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
        from colrev_core.environment import LocalIndex

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        # Note: Because we only introduce individual (non-merged records),
        # there should be no semicolons in origin!
        records_queue = [
            x
            for x in records
            if x["status"]
            not in [RecordState.md_imported, RecordState.md_needs_manual_preparation]
        ]

        # Do not merge records with non_latin_alphabets:
        records_queue = [
            x
            for x in records_queue
            if not (
                RecordState.prescreen_excluded == x["status"]
                and "script:non_latin_alphabet" == x.get("prescreen_exclusion", "")
            )
        ]

        LOCAL_INDEX = LocalIndex(self.REVIEW_MANAGER)
        for r in records_queue:
            r["colrev_ID"] = LOCAL_INDEX.get_colrev_ID(r)

        references = pd.DataFrame.from_dict(records_queue)
        references = self.__prep_references(references)

        return references

    def setup_active_learning_dedupe(self, retrain: bool):

        import dedupe
        from pathlib import Path

        logging.getLogger("dedupe.training").setLevel(logging.WARNING)
        logging.getLogger("dedupe.api").setLevel(logging.WARNING)

        training_file = Path(".references_dedupe_training.json")
        settings_file = Path(".references_learned_settings")
        if retrain:
            training_file.unlink(missing_ok=True)
            settings_file.unlink(missing_ok=True)

        self.REVIEW_MANAGER.logger.info("Importing data ...")

        ret_dict = {}

        # Possible extension: in the readData, we may want to append the status
        # to use Gazetteer (dedupe_io) if applicable (no duplicates in pos-md_processed)

        data_d = self.__readData()
        if len(data_d) < 50:
            ret_dict["status"] = "not_enough_data"

        else:

            self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(data_d))

            def title_corpus():
                for record in data_d.values():
                    yield record["title"]

            def container_corpus():
                for record in data_d.values():
                    yield record["container_title"]

            def author_corpus():
                for record in data_d.values():
                    yield record["author"]

            # Training

            # Define the fields dedupe will pay attention to
            fields = [
                {
                    "field": "author",
                    "type": "Text",
                    "corpus": author_corpus(),
                    "has missing": True,
                },
                {"field": "title", "type": "Text", "corpus": title_corpus()},
                {
                    "field": "container_title",
                    "type": "Text",
                    "corpus": container_corpus(),
                },
                {"field": "year", "type": "DateTime"},
                {"field": "volume", "type": "Text", "has missing": True},
                {"field": "number", "type": "Text", "has missing": True},
                {"field": "pages", "type": "String", "has missing": True},
            ]

            # Create a new deduper object and pass our data model to it.
            deduper = dedupe.Dedupe(fields)

            # If we have training data saved from a previous run of dedupe,
            # look for it and load it in.
            # __Note:__ if you want to train from scratch, delete the training_file
            if training_file.is_file():
                self.REVIEW_MANAGER.logger.info(
                    f"Reading pre-labeled training data from {training_file.name}"
                )
                with open(training_file, "rb") as f:
                    deduper.prepare_training(data_d, f)
            else:
                deduper.prepare_training(data_d)

            ret_dict["status"] = "ok"
            ret_dict["deduper"] = deduper

        return ret_dict

    def merge_r1_r2(self, main_record: dict, dupe_record: dict) -> dict:

        origins = main_record["origin"].split(";") + dupe_record["origin"].split(";")
        main_record["origin"] = ";".join(list(set(origins)))

        if "CURATED" != main_record.get("metadata_source", ""):
            for k in self.md_keys:
                if k in dupe_record and k not in main_record:
                    main_record[k] = dupe_record[k]

        if "pages" in dupe_record and "pages" not in main_record:
            main_record["pages"] = dupe_record["pages"]

        for k in self.complementary_keys:
            if k in dupe_record and k not in main_record:
                main_record[k] = dupe_record[k]

        if "file" in main_record and "file" in dupe_record:
            main_record["file"] = (
                main_record["file"] + ";" + dupe_record.get("file", "")
            )
        elif "file" in dupe_record and "file" not in main_record:
            main_record["file"] = dupe_record["file"]

        return main_record

    def apply_merges(self, results: list):
        """Apply automated deduplication decisions

        Level: IDs (not origins), requiring IDs to be immutable after md_prepared

        record['status'] can only be set to md_processed after running the
        active-learning classifier and checking whether the record is not part of
        any other duplicate-cluster
        - If the results list does not contain a 'score' value, it is generated
        manually and we cannot set the 'status' to md_processed
        - If the results list contains a 'score value'

        """

        # The merging also needs to consider whether IDs are propagated
        # Completeness of comparisons should be ensured by the
        # append_merges procedure (which ensures that all prior records
        # in global queue_order are considered before completing
        # the comparison/adding records ot the csvs)

        # results = list(itertools.chain(*results))

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        for non_dupe in [x["ID1"] for x in results if "no_duplicate" == x["decision"]]:
            non_dupe_record_list = [x for x in records if x["ID"] == non_dupe]
            if len(non_dupe_record_list) == 0:
                continue
            non_dupe_record = non_dupe_record_list.pop()
            non_dupe_record.update(status=RecordState.md_processed)

        for dupe in [x for x in results if "duplicate" == x["decision"]]:

            rec_ID1_list = [x for x in records if x["ID"] == dupe["ID1"]]
            rec_ID2_list = [x for x in records if x["ID"] == dupe["ID2"]]
            if len(rec_ID1_list) == 0 or len(rec_ID2_list) == 0:
                continue

            # Heuristic: Merge into curated record
            if "CURATED" == rec_ID2_list[0].get("metadata_source", ""):
                main_record = rec_ID2_list[0]
                dupe_record = rec_ID1_list[0]
            else:
                main_record = rec_ID1_list[0]
                dupe_record = rec_ID2_list[0]

            main_record = self.merge_r1_r2(main_record, dupe_record)

            if "score" in dupe:
                conf_details = f"(confidence: {str(round(dupe['score'], 3))})"
            else:
                conf_details = ""
            self.REVIEW_MANAGER.report_logger.info(
                f"Removed duplicate{conf_details}: "
                + f'{main_record["ID"]} <- {dupe_record["ID"]}'
            )

            records = [x for x in records if x["ID"] != dupe_record["ID"]]

        # Set remaining records to md_processed (not duplicate) because all records
        # have been considered by dedupe
        for record in records:
            if record["status"] == RecordState.md_prepared:
                record["status"] = RecordState.md_processed

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def apply_manual_deduplication_decisions(self, results: list):
        """Apply manual deduplication decisions

        Level: IDs (not origins), requiring IDs to be immutable after md_prepared

        Note : record['status'] can only be set to md_processed after running the
        active-learning classifier and checking whether the record is not part of
        any other duplicate-cluster
        """

        # The merging also needs to consider whether IDs are propagated

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        non_dupe_list = []
        dupe_list = []
        for x in results:
            if "no_duplicate" == x["decision"]:
                non_dupe_list.append([x["ID1"], x["ID2"]])
            if "duplicate" == x["decision"]:
                dupe_list.append([x["ID1"], x["ID2"]])

        # Set manual_non_duplicate marks
        for non_dupe_1, non_dupe_2 in non_dupe_list:
            record = [x for x in records if x["ID"] == non_dupe_1].pop()
            if "manual_non_duplicate" in record:
                id_list = record["manual_non_duplicate"].split(";") + [non_dupe_2]
                id_list = list(set(id_list))
                record["manual_non_duplicate"] = ";".join(id_list)
            else:
                record["manual_non_duplicate"] = non_dupe_2
            record = [x for x in records if x["ID"] == non_dupe_2].pop()
            if "manual_non_duplicate" in record:
                id_list = record["manual_non_duplicate"].split(";") + [non_dupe_1]
                id_list = list(set(id_list))
                record["manual_non_duplicate"] = ";".join(id_list)
            else:
                record["manual_non_duplicate"] = non_dupe_1

            # Note : no need to consider "manual_duplicate" (it stays the same)

        removed_duplicates = []
        for ID1, ID2 in dupe_list:
            rec_ID1_l = [x for x in records if x["ID"] == ID1]
            rec_ID2_l = [x for x in records if x["ID"] == ID2]
            if len(rec_ID1_l) != 1 or len(rec_ID2_l) != 1:
                continue

            rec_ID1 = rec_ID1_l[0]
            rec_ID2 = rec_ID2_l[0]

            # Heuristic: Merge into curated record
            if "CURATED" == rec_ID2.get("metadata_source", ""):
                main_record = rec_ID2
                dupe_record = rec_ID1
            else:
                main_record = rec_ID1
                dupe_record = rec_ID2

            dupe_rec_id = dupe_record["ID"]
            main_rec_id = main_record["ID"]

            # Simple way of implementing the closure
            # cases where the main_record has already been merged into another record
            if "MOVED_DUPE" in main_record:
                main_record = [
                    x for x in records if x["ID"] == main_record["MOVED_DUPE"]
                ].pop()

            dupe_record["MOVED_DUPE"] = main_record["ID"]

            main_record = self.merge_r1_r2(main_record, dupe_record)

            if "manual_duplicate" in main_record:
                main_record["manual_duplicate"] = (
                    main_record["manual_duplicate"] + ";" + dupe_rec_id
                )
            else:
                main_record["manual_duplicate"] = dupe_rec_id

            # Note: no need to change "manual_non_duplicate" or "manual_duplicate"
            # in dupe_record because dupe_record will be dropped anyway

            if (
                "manual_non_duplicate" in main_record
                and "manual_non_duplicate" in dupe_record
            ):
                main_record["manual_non_duplicate"] = (
                    main_record["manual_non_duplicate"]
                    + ";"
                    + dupe_record["manual_non_duplicate"]
                )

            # Note : we add the "manual_duplicate" from dedupe record to keep all
            # manual_duplicate classification decisions
            if "manual_duplicate" in dupe_record:
                if "manual_duplicate" in main_record:
                    main_record["manual_duplicate"] = (
                        main_record["manual_duplicate"]
                        + ";"
                        + dupe_record["manual_duplicate"]
                    )
                else:
                    main_record["manual_duplicate"] = dupe_record["manual_duplicate"]

            self.REVIEW_MANAGER.report_logger.info(
                f"Removed duplicate: {dupe_rec_id} (duplicate of {main_rec_id})"
            )
            removed_duplicates.append(dupe_rec_id)

        records = [x for x in records if x["ID"] not in removed_duplicates]

        records = [{k: v for k, v in r.items() if k != "MOVED_DUPE"} for r in records]

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def fix_errors(self) -> None:
        """Errors are highlighted in the Excel files"""

        import bibtexparser

        self.REVIEW_MANAGER.report_logger.info("Dedupe: fix errors")
        self.REVIEW_MANAGER.logger.info("Dedupe: fix errors")
        saved_args = locals()

        dupe_file = Path("duplicates_to_validate.xlsx")
        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        if dupe_file.is_file():
            dupes = pd.read_excel(dupe_file)
            dupes.fillna("", inplace=True)
            c_to_correct = dupes.loc[dupes["error"] != "", "cluster_id"].to_list()
            dupes = dupes[dupes["cluster_id"].isin(c_to_correct)]
            IDs_to_unmerge = dupes.groupby(["cluster_id"])["ID"].apply(list).tolist()

            if len(IDs_to_unmerge) > 0:
                records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

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
                while len(IDs_to_unmerge) > 0:
                    filecontents = next(revlist)
                    prior_db = bibtexparser.loads(filecontents)
                    prior_records = prior_db.entries

                    unmerged = []
                    for ID_list_to_unmerge in IDs_to_unmerge:
                        self.REVIEW_MANAGER.report_logger.info(
                            f'Undo merge: {",".join(ID_list_to_unmerge)}'
                        )

                        # delete new record,
                        # add previous records (from history) to records
                        records = [
                            r for r in records if r["ID"] not in ID_list_to_unmerge
                        ]

                        if all(
                            [
                                ID in [r["ID"] for r in prior_records]
                                for ID in ID_list_to_unmerge
                            ]
                        ):
                            for r in prior_records:
                                if r["ID"] in ID_list_to_unmerge:
                                    # add manual_dedupe/non_dupe decision to the records
                                    manual_non_duplicates = ID_list_to_unmerge.copy()
                                    manual_non_duplicates.remove(r["ID"])

                                    if "manual_non_duplicate" in r:
                                        r["manual_non_duplicate"] = (
                                            r["manual_non_duplicate"]
                                            + ";"
                                            + ";".join(manual_non_duplicates)
                                        )
                                    else:
                                        r["manual_non_duplicate"] = ";".join(
                                            manual_non_duplicates
                                        )
                                    r["status"] = RecordState.md_processed
                                    records.append(r)
                                    self.REVIEW_MANAGER.logger.info(
                                        f'Restored {r["ID"]}'
                                    )
                        else:
                            unmerged.append(ID_list_to_unmerge)

                    IDs_to_unmerge = unmerged

                records = sorted(records, key=lambda d: d["ID"])
                self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
                self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        non_dupe_file_xlsx = Path("non_duplicates_to_validate.xlsx")
        non_dupe_file_txt = Path("dupes.txt")
        if non_dupe_file_xlsx.is_file() or non_dupe_file_txt.is_file():
            IDs_to_merge = []
            if non_dupe_file_xlsx.is_file():
                non_dupes = pd.read_excel(non_dupe_file_xlsx)
                non_dupes.fillna("", inplace=True)
                c_to_correct = non_dupes.loc[
                    non_dupes["error"] != "", "cluster_id"
                ].to_list()
                non_dupes = non_dupes[non_dupes["cluster_id"].isin(c_to_correct)]
                IDs_to_merge = (
                    non_dupes.groupby(["cluster_id"])["ID"].apply(list).tolist()
                )
            if non_dupe_file_txt.is_file():
                content = non_dupe_file_txt.read_text()
                IDs_to_merge = [x.split(",") for x in content.splitlines()]
                for ID1, ID2 in IDs_to_merge:
                    print(ID1 + ID2)

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
                self.apply_manual_deduplication_decisions(auto_dedupe)

        if (
            dupe_file.is_file()
            or non_dupe_file_xlsx.is_file()
            or non_dupe_file_txt.is_file()
        ):
            self.REVIEW_MANAGER.create_commit(
                "Validate and correct duplicates",
                manual_author=True,
                saved_args=saved_args,
            )
        else:
            self.REVIEW_MANAGER.logger.error("No file with potential errors found.")
        return

    def cluster_tuples(self, deduper, partition_threshold, auto_merge_threshold):

        self.REVIEW_MANAGER.logger.info("Clustering duplicates...")

        data_d = self.__readData()
        self.REVIEW_MANAGER.logger.info(f"Number of records: {len(data_d.items())}")

        # `partition` will return sets of records that dedupe
        # believes are all referring to the same entity.

        self.REVIEW_MANAGER.report_logger.info(
            f"set partition_threshold: {partition_threshold}"
        )

        clustered_dupes = deduper.partition(data_d, partition_threshold)
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
                    "score": list(scores).pop(),
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
            f"set auto_merge_threshold: {auto_merge_threshold}"
        )
        for dedupe_decision in dedupe_decision_list:

            if len(dedupe_decision["records"]) > 1:
                if dedupe_decision["score"] > auto_merge_threshold:
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
                            self.REVIEW_MANAGER.REVIEW_DATASET.propagated_ID(orig_rec)
                        )
                        dupe_propagated = (
                            self.REVIEW_MANAGER.REVIEW_DATASET.propagated_ID(dupe_rec)
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

        self.apply_merges(auto_dedupe)

        self.REVIEW_MANAGER.reorder_log(ID_list, criterion="descending_thresholds")

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
            cur_cluster_membership = cluster_membership[ID]
            vals.update(cur_cluster_membership)
            if cur_cluster_membership["confidence_score"] > auto_merge_threshold:
                collected_duplicates.append(vals)
            else:
                collected_non_duplicates.append(vals)

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
        duplicates_df = duplicates_df.style.apply(highlight_cells, axis=None)
        duplicates_df.to_excel("duplicates_to_validate.xlsx", index=False)

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
            non_duplicates_df.to_excel("non_duplicates_to_validate.xlsx", index=False)

        return

    def view_info(self) -> dict:
        import itertools

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

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        origins = [record["origin"].split(";") for record in records]
        origins = [item.split("/")[0] for sublist in origins for item in sublist]
        origins = list(set(origins))

        cuts = {}
        for L in range(1, len(origins) + 1):
            for subset in itertools.combinations(origins, L):
                cuts["/".join(list(subset))] = {"origins": list(subset), "records": []}

        for record in records:
            rec_origins = list({x.split("/")[0] for x in record["origin"].split(";")})
            cut_list = [x for k, x in cuts.items() if x["origins"] == rec_origins]
            if len(cut_list) != 1:
                print(record["ID"])
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

        total = len(records)
        for k, det in cuts.items():
            det["size"] = len(det["records"])  # type: ignore
            det["fraction"] = det["size"] / total * 100  # type: ignore

        info = {"cuts": cuts}
        return info


if __name__ == "__main__":
    pass
