#! /usr/bin/env python
"""CoLRev dedupe operation: identify and merge duplicate records."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record
import colrev.ui_cli.cli_colors as colors

if TYPE_CHECKING:
    import colrev.review_manager


class Dedupe(colrev.process.Process):

    SIMPLE_SIMILARITY_BASED_DEDUPE = "simple_similarity_based_dedupe"
    ACTIVE_LEARNING_DEDUPE = "active_learning_dedupe"
    ACTIVE_LEARNING_NON_MEMORY_DEDUPE = "active_learning_non_memory_dedupe"

    training_file: Path
    settings_file: Path
    non_dupe_file_xlsx: Path
    dupe_file: Path

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation=True,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.dedupe,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.training_file = self.review_manager.path / Path(
            ".records_dedupe_training.json"
        )
        self.settings_file = self.review_manager.path / Path(
            ".records_learned_settings"
        )
        self.non_dupe_file_xlsx = self.review_manager.path / Path(
            "non_duplicates_to_validate.xlsx"
        )
        self.non_dupe_file_txt = self.review_manager.path / Path("dupes.txt")
        self.dupe_file = self.review_manager.path / Path("duplicates_to_validate.xlsx")
        self.source_comparison_xlsx = self.review_manager.path / Path(
            "source_comparison.xlsx"
        )

        self.review_manager.report_logger.info("Dedupe")
        self.review_manager.logger.info("Dedupe")

    def prep_records(self, *, records_df: pd.DataFrame) -> dict:
        def pre_process(*, key, value):
            if key in ["ID", "ENTRYTYPE", "colrev_status", "colrev_origin"]:
                return value

            value = str(value)
            if any(
                value == x
                for x in ["no issue", "no volume", "no pages", "no author", "nan"]
            ):
                value = None
                return value

            # Note unidecode may be an alternative to rmdiacritics/remove_accents.
            # It would be important to operate on a per-character basis
            # instead of throwing an exception when processing whole strings
            # value = unidecode(value)
            value = re.sub("  +", " ", value)
            value = re.sub("\n", " ", value)
            value = value.strip().strip('"').strip("'").lower().strip()
            # If data is missing, indicate that by setting the value to `None`
            if not value:
                value = None
            return value

        if "colrev_status" in records_df:
            records_df["colrev_status"] = records_df["colrev_status"].astype(str)

        if "volume" not in records_df:
            records_df["volume"] = "nan"
        if "number" not in records_df:
            records_df["number"] = "nan"
        if "pages" not in records_df:
            records_df["pages"] = "nan"
        if "year" not in records_df:
            records_df["year"] = "nan"
        else:
            records_df["year"] = records_df["year"].astype(str)
        if "author" not in records_df:
            records_df["author"] = "nan"

        records_df["author"] = records_df["author"].str[:60]

        records_df.loc[
            records_df.ENTRYTYPE == "inbook", "container_title"
        ] = records_df.loc[records_df.ENTRYTYPE == "inbook", "title"]
        if "chapter" in records_df:
            records_df.loc[records_df.ENTRYTYPE == "inbook", "title"] = records_df.loc[
                records_df.ENTRYTYPE == "inbook", "chapter"
            ]

        if "title" not in records_df:
            records_df["title"] = "nan"
        else:
            records_df["title"] = (
                records_df["title"]
                .str.replace(r"[^A-Za-z0-9, ]+", " ", regex=True)
                .str.lower()
            )
            records_df.loc[records_df["title"].isnull(), "title"] = "nan"

        if "journal" not in records_df:
            records_df["journal"] = ""
        else:
            records_df["journal"] = (
                records_df["journal"]
                .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
                .str.lower()
            )
        if "booktitle" not in records_df:
            records_df["booktitle"] = ""
        else:
            records_df["booktitle"] = (
                records_df["booktitle"]
                .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
                .str.lower()
            )

        if "series" not in records_df:
            records_df["series"] = ""
        else:
            records_df["series"] = (
                records_df["series"]
                .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
                .str.lower()
            )

        records_df["container_title"] = (
            records_df["journal"].fillna("")
            + records_df["booktitle"].fillna("")
            + records_df["series"].fillna("")
        )

        # To validate/improve preparation in jupyter notebook:
        # return records_df
        # Copy to notebook:
        # from colrev.review_manager import ReviewManager
        # from colrev.process import Process, ProcessType
        # review_manager = ReviewManager()
        # df = self.read_data(review_manager)
        # EDITS
        # df.to_csv('export.csv', index=False)

        records_df.drop(
            labels=records_df.columns.difference(
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
            axis=1,
            inplace=True,
        )
        records_df[
            ["author", "title", "journal", "container_title", "pages"]
        ] = records_df[
            ["author", "title", "journal", "container_title", "pages"]
        ].astype(
            str
        )
        records_list = records_df.to_dict("records")
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(records_list)
        )

        records = {}

        for row in records_list:
            # Note: we need the ID to identify/remove duplicates in the RECORDS_FILE.
            # It is ignored in the field-definitions by the deduper!
            # clean_row = [(k, pre_process(k, v)) for (k, v) in row.items() if k != "ID"]
            clean_row = [(k, pre_process(key=k, value=v)) for (k, v) in row.items()]
            records[row["ID"]] = dict(clean_row)

        return records

    def read_data(self) -> dict:

        records = self.review_manager.dataset.load_records_dict()

        # Note: Because we only introduce individual (non-merged records),
        # there should be no semicolons in colrev_origin!
        records_queue = [
            x
            for x in records.values()
            if x["colrev_status"]
            not in [
                colrev.record.RecordState.md_imported,
                colrev.record.RecordState.md_needs_manual_preparation,
            ]
        ]

        # Do not merge records with non_latin_alphabets:
        records_queue = [
            record_dict
            for record_dict in records_queue
            if not (
                colrev.record.RecordState.rev_prescreen_excluded
                == record_dict["colrev_status"]
                and "script:non_latin_alphabet"
                == record_dict.get("prescreen_exclusion", "")
            )
        ]

        for record_dict in records_queue:
            try:
                record = colrev.record.Record(data=record_dict)
                record_dict["colrev_id"] = record.create_colrev_id()
            except colrev_exceptions.NotEnoughDataToIdentifyException:
                record_dict["colrev_id"] = "NA"

        records_df = pd.DataFrame.from_dict(records_queue)
        records = self.prep_records(records_df=records_df)

        return records

    def select_primary_merge_record(self, rec_id_1: dict, rec_id_2: dict) -> list:
        # Note : named parameters not useful

        # Heuristic

        # 1. if both records are prepared (or the same status),
        # merge into the record with the lower colrev_id
        if rec_id_1["colrev_status"] == rec_id_2["colrev_status"]:
            if rec_id_1["ID"][-1].isdigit() and not rec_id_2["ID"][-1].isdigit():
                main_record = rec_id_1
                dupe_record = rec_id_2
            # TODO : elif: check which of the appended letters is first in the alphabet
            else:
                main_record = rec_id_2
                dupe_record = rec_id_1

        # 2. If a record is md_prepared, use it as the dupe record
        elif rec_id_1["colrev_status"] == colrev.record.RecordState.md_prepared:
            main_record = rec_id_2
            dupe_record = rec_id_1
        elif rec_id_2["colrev_status"] == colrev.record.RecordState.md_prepared:
            main_record = rec_id_1
            dupe_record = rec_id_2

        # 3. If a record is md_processed, use the other record as the dupe record
        # -> during the fix_errors procedure, records are in md_processed
        # and beyond.
        elif rec_id_1["colrev_status"] == colrev.record.RecordState.md_processed:
            main_record = rec_id_1
            dupe_record = rec_id_2
        elif rec_id_2["colrev_status"] == colrev.record.RecordState.md_processed:
            main_record = rec_id_2
            dupe_record = rec_id_1

        # 4. Merge into curated record (otherwise)
        else:
            if colrev.record.Record(data=rec_id_2).masterdata_is_curated():
                main_record = rec_id_2
                dupe_record = rec_id_1
            else:
                main_record = rec_id_1
                dupe_record = rec_id_2
        return [main_record, dupe_record]

    def apply_merges(self, *, results: list, remaining_non_dupe: bool = False) -> None:
        """Apply automated deduplication decisions

        Level: IDs (not colrev_origins), requiring IDs to be immutable after md_prepared

        record['colrev_status'] can only be set to md_processed after running the
        active-learning classifier and checking whether the record is not part of
        any other duplicate-cluster
        - If the results list does not contain a 'score' value, it is generated
        manually and we cannot set the 'colrev_status' to md_processed
        - If the results list contains a 'score value'

        """

        # The merging also needs to consider whether IDs are propagated
        # Completeness of comparisons should be ensured by the
        # dedupe clustering routine

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
            with same_source_merge_file.open("a", encoding="utf8") as file:
                file.write(merge_info + "\n")
            self.review_manager.logger.warning(
                f"Prevented same-source merge: ({merge_info})"
            )

        def cross_level_merge(main_record: dict, dupe_record: dict) -> bool:
            cross_level_merge_attempt = False
            if main_record["ENTRYTYPE"] in ["proceedings"] or dupe_record[
                "ENTRYTYPE"
            ] in ["proceedings"]:
                cross_level_merge_attempt = True
            # TODO: book vs. inbook?
            return cross_level_merge_attempt

        records = self.review_manager.dataset.load_records_dict()

        for non_dupe in [x["ID1"] for x in results if "no_duplicate" == x["decision"]]:
            if non_dupe in records:
                records[non_dupe].update(
                    colrev_status=colrev.record.RecordState.md_processed
                )

        removed_duplicates = []
        duplicates_to_process = [x for x in results if "duplicate" == x["decision"]]
        for dupe in duplicates_to_process:

            rec_id_1 = records[dupe["ID1"]]
            rec_id_2 = records[dupe["ID2"]]

            # Simple way of implementing the closure
            # cases where the main_record has already been merged into another record
            while "MOVED_DUPE" in rec_id_1:
                rec_id_1 = records[rec_id_1["MOVED_DUPE"]]
            while "MOVED_DUPE" in rec_id_2:
                rec_id_2 = records[rec_id_2["MOVED_DUPE"]]
            if rec_id_1["ID"] == rec_id_2["ID"]:
                continue

            main_record_dict, dupe_record_dict = self.select_primary_merge_record(
                rec_id_1, rec_id_2
            )

            if cross_level_merge(main_record_dict, dupe_record_dict):
                continue

            if same_source_merge(main_record_dict, dupe_record_dict):
                if "apply" != self.review_manager.settings.dedupe.same_source_merges:
                    main_record = colrev.record.Record(data=main_record_dict)
                    dupe_record = colrev.record.Record(data=dupe_record_dict)
                    print(
                        f"\n{colors.ORANGE}"
                        "Warning: applying same source merge "
                        f"{colors.END} "
                        f"{main_record_dict.get('colrev_origin', '')}/"
                        f"{dupe_record_dict.get('colrev_origin', '')}\n"
                        f"  {main_record.format_bib_style()}\n"
                        f"  {dupe_record.format_bib_style()}"
                    )
                elif (
                    "prevent" == self.review_manager.settings.dedupe.same_source_merges
                ):
                    export_same_source_merge(main_record_dict, dupe_record_dict)
                    continue  # with next pair
                else:
                    print(
                        "Invalid setting: dedupe.same_source_merges: "
                        f"{self.review_manager.settings.dedupe.same_source_merges}"
                    )
                    continue  # with next pair

            dupe_record_dict["MOVED_DUPE"] = main_record_dict["ID"]
            main_record = colrev.record.Record(data=main_record_dict)
            dupe_record.merge(
                merging_record=colrev.record.Record(data=dupe_record_dict),
                default_source="merged",
            )
            # main_record = MAIN_RECORD.get_data()

            conf_details = (
                f"(confidence: {str(round(dupe['score'], 3))})"
                if "score" in dupe
                else ""
            )

            self.review_manager.logger.debug(
                f"Removed duplicate{conf_details}: "
                + f'{main_record_dict["ID"]} <- {dupe_record_dict["ID"]}'
            )

            removed_duplicates.append(dupe_record_dict["ID"])

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
                if record["colrev_status"] == colrev.record.RecordState.md_prepared:
                    record["colrev_status"] = colrev.record.RecordState.md_processed

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

    def apply_manual_deduplication_decisions(self, *, results: list) -> None:
        """Apply manual deduplication decisions

        Level: IDs (not colrev_origins), requiring IDs to be immutable after md_prepared

        Note : record['colrev_status'] can only be set to md_processed after running the
        active-learning classifier and checking whether the record is not part of
        any other duplicate-cluster
        """

        # The merging also needs to consider whether IDs are propagated

        records = self.review_manager.dataset.load_records_dict()

        non_dupe_list = []
        dupe_list = []
        for decision in results:
            if "no_duplicate" == decision["decision"]:
                non_dupe_list.append([decision["ID1"], decision["ID2"]])
            if "duplicate" == decision["decision"]:
                dupe_list.append([decision["ID1"], decision["ID2"]])

        removed_duplicates = []
        for id_1, id_2 in dupe_list:

            rec_id_1 = records[id_1]
            rec_id_2 = records[id_2]

            self.review_manager.logger.debug(
                f'applying {rec_id_1["ID"]}-{rec_id_2["ID"]}'
            )

            # Simple way of implementing the closure
            # cases where the main_record has already been merged into another record
            while "MOVED_DUPE" in rec_id_1:
                rec_id_1 = records[rec_id_1["MOVED_DUPE"]]
            while "MOVED_DUPE" in rec_id_2:
                rec_id_2 = records[rec_id_2["MOVED_DUPE"]]

            if rec_id_1["ID"] == rec_id_2["ID"]:
                continue

            main_record_dict, dupe_record_dict = self.select_primary_merge_record(
                rec_id_1, rec_id_2
            )

            # TODO : prevent same-source merges (like in the automated part?!)
            dupe_rec_id = dupe_record_dict["ID"]
            main_rec_id = main_record_dict["ID"]
            self.review_manager.logger.debug(main_rec_id + " < " + dupe_rec_id)

            dupe_record_dict["MOVED_DUPE"] = main_record_dict["ID"]
            main_record = colrev.record.Record(data=main_record_dict)
            main_record.merge(
                merging_record=colrev.record.Record(data=dupe_record_dict),
                default_source="merged",
            )
            # main_record = main_record.get_data()

            self.review_manager.logger.debug(
                f"Removed duplicate: {dupe_rec_id} (duplicate of {main_rec_id})"
            )
            removed_duplicates.append(dupe_rec_id)

        for record in records.values():
            if "MOVED_DUPE" in record:
                del record["MOVED_DUPE"]
        for removed_duplicate in removed_duplicates:
            if removed_duplicate in records:
                del records[removed_duplicate]

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

    def source_comparison(self) -> None:
        """Exports a spreadsheet to support analyses of records that are not
        in all sources (for curated repositories)"""

        source_filenames = [x.filename for x in self.review_manager.settings.sources]
        print("sources: " + ",".join([str(x) for x in source_filenames]))

        records = self.review_manager.dataset.load_records_dict()
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

    def fix_errors(self) -> None:
        """Fix errors as highlighted in the Excel files"""

        self.review_manager.report_logger.info("Dedupe: fix errors")
        self.review_manager.logger.info("Dedupe: fix errors")
        saved_args = locals()

        git_repo = self.review_manager.dataset.get_repo()
        if self.dupe_file.is_file():
            dupes = pd.read_excel(self.dupe_file)
            dupes.fillna("", inplace=True)
            c_to_correct = dupes.loc[dupes["error"] != "", "cluster_id"].to_list()
            dupes = dupes[dupes["cluster_id"].isin(c_to_correct)]
            ids_to_unmerge = dupes.groupby(["cluster_id"])["ID"].apply(list).tolist()

            if len(ids_to_unmerge) > 0:
                records = self.review_manager.dataset.load_records_dict()

                revlist = (
                    (
                        (
                            commit.tree
                            / str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                        ).data_stream.read()
                    )
                    for commit in git_repo.iter_commits(
                        paths=str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                    )
                )

                # Note : there could be more than two IDs in the list
                filecontents = next(revlist)

                prior_records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=filecontents.decode("utf-8")
                )

                for id_list_to_unmerge in ids_to_unmerge:
                    self.review_manager.report_logger.info(
                        f'Undo merge: {",".join(id_list_to_unmerge)}'
                    )

                    # delete new record,
                    # add previous records (from history) to records
                    records = {
                        k: v for k, v in records.items() if k not in id_list_to_unmerge
                    }

                    if all(ID in prior_records_dict for ID in id_list_to_unmerge):
                        for record_dict in prior_records_dict.values():
                            if record_dict["ID"] in id_list_to_unmerge:
                                # add manual_dedupe/non_dupe decision to the records
                                manual_non_duplicates = id_list_to_unmerge.copy()
                                manual_non_duplicates.remove(record_dict["ID"])

                                record_dict[
                                    "colrev_status"
                                ] = colrev.record.RecordState.md_processed
                                r_dict = {record_dict["ID"]: record_dict}
                                records[r_dict["ID"]] = r_dict
                                self.review_manager.logger.info(
                                    f'Restored {record_dict["ID"]}'
                                )
                    else:
                        self.review_manager.logger.error(
                            f"Could not retore {id_list_to_unmerge} - "
                            "please fix manually"
                        )

                self.review_manager.dataset.save_records_dict(records=records)
                self.review_manager.dataset.add_record_changes()

        if self.non_dupe_file_xlsx.is_file() or self.non_dupe_file_txt.is_file():
            ids_to_merge = []
            if self.non_dupe_file_xlsx.is_file():
                non_dupes = pd.read_excel(self.non_dupe_file_xlsx)
                non_dupes.fillna("", inplace=True)
                c_to_correct = non_dupes.loc[
                    non_dupes["error"] != "", "cluster_id"
                ].to_list()
                non_dupes = non_dupes[non_dupes["cluster_id"].isin(c_to_correct)]
                ids_to_merge = (
                    non_dupes.groupby(["cluster_id"])["ID"].apply(list).tolist()
                )
            if self.non_dupe_file_txt.is_file():
                content = self.non_dupe_file_txt.read_text()
                ids_to_merge = [x.split(",") for x in content.splitlines()]
                for id_1, id_2 in ids_to_merge:
                    print(f"{id_1} - {id_2}")

            if len(ids_to_merge) > 0:
                auto_dedupe = []
                for id_1, id_2 in ids_to_merge:
                    auto_dedupe.append(
                        {
                            "ID1": id_1,
                            "ID2": id_2,
                            "decision": "duplicate",
                        }
                    )
                self.apply_manual_deduplication_decisions(results=auto_dedupe)

        if (
            self.dupe_file.is_file()
            or self.non_dupe_file_xlsx.is_file()
            or self.non_dupe_file_txt.is_file()
        ):
            self.review_manager.create_commit(
                msg="Validate and correct duplicates",
                manual_author=True,
                script_call="colrev dedupe",
                saved_args=saved_args,
            )
        else:
            self.review_manager.logger.error("No file with potential errors found.")

    def get_info(self) -> dict:
        """Get info on cuts (overlap of search sources) and same source merges"""

        records = self.review_manager.dataset.load_records_dict()

        origins = [record["colrev_origin"].split(";") for record in records.values()]
        origins = [item.split("/")[0] for sublist in origins for item in sublist]
        origins = list(set(origins))

        same_source_merges = []

        for record in records.values():

            rec_sources = [x.split("/")[0] for x in record["colrev_origin"].split(";")]

            duplicated_sources = [
                item for item, count in Counter(rec_sources).items() if count > 1
            ]
            if len(duplicated_sources) > 0:
                all_cases = []
                for duplicated_source in duplicated_sources:
                    cases = [
                        o.split("/")[1]
                        for o in record["colrev_origin"].split(";")
                        if duplicated_source in o
                    ]
                    all_cases.append(f"{duplicated_source}: {cases}")
                same_source_merges.append(f"{record['ID']} ({', '.join(all_cases)})")

        info = {
            "same_source_merges": same_source_merges,
        }
        return info

    def main(self) -> None:

        for dedupe_script in self.review_manager.settings.dedupe.scripts:

            # Note : load package/script at this point because the same script
            # may run with different parameters
            package_manager = self.review_manager.get_package_manager()
            endpoint_script = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageType.dedupe,
                selected_packages=[dedupe_script],
                process=self,
            )

            endpoint = endpoint_script[dedupe_script["endpoint"]]

            endpoint.run_dedupe(self)  # type: ignore
            print()


if __name__ == "__main__":
    pass
