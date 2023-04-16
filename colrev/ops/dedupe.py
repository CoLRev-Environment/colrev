#! /usr/bin/env python
"""CoLRev dedupe operation: identify and merge duplicate records."""
from __future__ import annotations

import re
import string
import typing
from collections import Counter
from pathlib import Path
from typing import Optional

import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record
import colrev.settings
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager

# pylint: disable=too-many-lines


class Dedupe(colrev.operation.Operation):
    """Deduplicate records (entity resolution)"""

    NON_DUPLICATE_FILE_XLSX = Path("non_duplicates_to_validate.xlsx")
    NON_DUPLICATE_FILE_TXT = Path("non_duplicates_to_validate.txt")
    DUPLICATES_TO_VALIDATE = Path("duplicates_to_validate.xlsx")
    SAME_SOURCE_MERGE_FILE = Path("same_source_merges.txt")
    PREVENTED_SAME_SOURCE_MERGE_FILE = Path("prevented_same_source_merges.txt")

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.dedupe,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.non_dupe_file_xlsx = (
            self.review_manager.dedupe_dir / self.NON_DUPLICATE_FILE_XLSX
        )
        self.non_dupe_file_txt = (
            self.review_manager.dedupe_dir / self.NON_DUPLICATE_FILE_TXT
        )
        self.dupe_file = self.review_manager.dedupe_dir / self.DUPLICATES_TO_VALIDATE

        self.same_source_merge_file = (
            self.review_manager.dedupe_dir / self.SAME_SOURCE_MERGE_FILE
        )
        self.prevented_same_source_merge_file = (
            self.review_manager.dedupe_dir / self.PREVENTED_SAME_SOURCE_MERGE_FILE
        )
        self.review_manager.dedupe_dir.mkdir(exist_ok=True, parents=True)

    def __pre_process(self, *, key: str, value: str) -> str | None:
        if key in ["ID", "ENTRYTYPE", "colrev_status", "colrev_origin"]:
            return value

        value = str(value)
        # Note unidecode may be an alternative to rmdiacritics/remove_accents.
        # It would be important to operate on a per-character basis
        # instead of throwing an exception when processing whole strings
        # value = unidecode(value)
        value = re.sub("  +", " ", value)
        value = re.sub("\n", " ", value)
        value = value.strip().strip('"').strip("'").lower().strip()
        # If data is missing, indicate that by setting the value to `None`
        if not value:
            return None

        if any(
            value == x
            for x in ["no issue", "no volume", "no pages", "no author", "nan", ""]
        ):
            return None

        return value

    def prep_records(self, *, records_df: pd.DataFrame) -> dict:
        """Prepare records for dedupe"""

        if 0 == records_df.shape[0]:
            return {}

        required_fields = [
            "journal",
            "journal",
            "booktitle",
            "series",
            "volume",
            "number",
            "pages",
            "author",
        ]
        for required_field in required_fields:
            if required_field not in records_df:
                records_df[required_field] = ""

        records_df["year"] = records_df["year"].astype(str)
        if "colrev_status" in records_df:
            # pylint: disable=direct-status-assign
            records_df["colrev_status"] = records_df["colrev_status"].astype(str)

        records_df["author"] = records_df["author"].str[:60]

        records_df.loc[
            records_df.ENTRYTYPE == "inbook", "container_title"
        ] = records_df.loc[records_df.ENTRYTYPE == "inbook", "title"]
        if "chapter" in records_df:
            records_df.loc[records_df.ENTRYTYPE == "inbook", "title"] = records_df.loc[
                records_df.ENTRYTYPE == "inbook", "chapter"
            ]

        records_df["title"] = (
            records_df["title"]
            .str.replace(r"[^A-Za-z0-9, ]+", " ", regex=True)
            .str.lower()
        )
        records_df.loc[records_df["title"].isnull(), "title"] = ""

        records_df["journal"] = (
            records_df["journal"]
            .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
            .str.lower()
        )

        records_df["booktitle"] = (
            records_df["booktitle"]
            .str.replace(r"[^A-Za-z0-9, ]+", "", regex=True)
            .str.lower()
        )

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
        # from colrev.operation import Operation, OperationsType
        # review_manager = ReviewManager()
        # df = self.read_data(review_manager)
        # EDITS
        # df.to_csv('export.csv', index=False)

        records_df.drop(
            labels=list(
                records_df.columns.difference(
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
                )
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

        records = {}
        for row in records_list:
            # Note: we need the ID to identify/remove duplicates in the RECORDS_FILE.
            # It is ignored in the field-definitions by the deduper
            clean_row = [
                (k, self.__pre_process(key=str(k), value=v)) for (k, v) in row.items()
            ]
            records[row["ID"]] = dict(clean_row)

        return records

    def read_data(self) -> dict:
        """Read the data for dedupe"""

        records = self.review_manager.dataset.load_records_dict()

        # Note: Because we only introduce individual (non-merged records),
        # the length of colrev_origin lists should be 1!
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
                and "non_latin_alphabet" in record_dict.get("prescreen_exclusion", "")
            )
        ]

        for record_dict in records_queue:
            try:
                record = colrev.record.Record(data=record_dict)
                record_dict["colrev_id"] = record.create_colrev_id()
            except colrev_exceptions.NotEnoughDataToIdentifyException:
                record_dict["colrev_id"] = "NA"

        records_df = pd.DataFrame.from_records(records_queue)
        records = self.prep_records(records_df=records_df)

        return records

    def __select_primary_merge_record(self, rec_1: dict, rec_2: dict) -> list:
        # pylint: disable=too-many-branches

        # Heuristic

        # 1. if both records are prepared (or the same status),
        # merge into the record with the "lower" colrev_id
        if rec_1["colrev_status"] == rec_2["colrev_status"]:
            if rec_1["ID"][-1].isdigit() and not rec_2["ID"][-1].isdigit():
                main_record = rec_1
                dupe_record = rec_2
            elif not rec_1["ID"][-1].isdigit() and not rec_2["ID"][-1].isdigit():
                # Last characters are letters in both records
                # Select the one that's first in the alphabet
                try:
                    pos_rec_1_suffix = string.ascii_lowercase.index(rec_1["ID"][-1])
                except ValueError:
                    pos_rec_1_suffix = -1
                try:
                    pos_rec_2_suffix = string.ascii_lowercase.index(rec_2["ID"][-1])
                except ValueError:
                    pos_rec_2_suffix = -1

                if pos_rec_1_suffix < pos_rec_2_suffix:
                    main_record = rec_1
                    dupe_record = rec_2
                else:
                    dupe_record = rec_2
                    main_record = rec_1
            else:
                main_record = rec_2
                dupe_record = rec_1

        # 2. If a record is md_prepared, use it as the dupe record
        elif rec_1["colrev_status"] == colrev.record.RecordState.md_prepared:
            main_record = rec_2
            dupe_record = rec_1
        elif rec_2["colrev_status"] == colrev.record.RecordState.md_prepared:
            main_record = rec_1
            dupe_record = rec_2

        # 3. If a record is md_processed, use the other record as the dupe record
        # -> during the fix_errors procedure, records are in md_processed
        # and beyond.
        elif rec_1["colrev_status"] == colrev.record.RecordState.md_processed:
            main_record = rec_1
            dupe_record = rec_2
        elif rec_2["colrev_status"] == colrev.record.RecordState.md_processed:
            main_record = rec_2
            dupe_record = rec_1

        # 4. Merge into curated record (otherwise)
        else:
            if colrev.record.Record(data=rec_2).masterdata_is_curated():
                main_record = rec_2
                dupe_record = rec_1
            else:
                main_record = rec_1
                dupe_record = rec_2

        return [main_record, dupe_record]

    def __same_source_merge(
        self, *, main_record: colrev.record.Record, dupe_record: colrev.record.Record
    ) -> bool:
        main_rec_sources = [x.split("/")[0] for x in main_record.data["colrev_origin"]]
        dupe_rec_sources = [x.split("/")[0] for x in dupe_record.data["colrev_origin"]]
        same_sources = set(main_rec_sources).intersection(set(dupe_rec_sources))

        if len(same_sources) == 0:
            return False

        # don't raise unproblematic same-source merges
        # if same_sources start with md_... AND have same IDs: no same-source merge.
        if all(x.startswith("md_") for x in same_sources):
            main_rec_same_source_origins = [
                x
                for x in main_record.data["colrev_origin"]
                if x.split("/")[0] in same_sources
            ]
            dupe_rec_same_source_origins = [
                x
                for x in dupe_record.data["colrev_origin"]
                if x.split("/")[0] in same_sources
            ]
            if set(main_rec_same_source_origins) == set(dupe_rec_same_source_origins):
                return False
            return True
        return True

    def __export_same_source_merge(
        self, *, main_record: colrev.record.Record, dupe_record: colrev.record.Record
    ) -> None:
        if (
            colrev.settings.SameSourceMergePolicy.apply
            == self.review_manager.settings.dedupe.same_source_merges
        ):
            return

        merge_info = main_record.data["ID"] + "," + dupe_record.data["ID"]

        if (
            colrev.settings.SameSourceMergePolicy.warn
            == self.review_manager.settings.dedupe.same_source_merges
        ):
            self.review_manager.logger.warning(
                f"\n{colors.ORANGE}"
                "Applying same source merge "
                f"{colors.END} "
                f"{main_record.data.get('colrev_origin', ['ERROR'])}/"
                f"{dupe_record.data.get('colrev_origin', ['ERROR'])}\n"
                f"  {main_record.format_bib_style()}\n"
                f"  {dupe_record.format_bib_style()}"
            )
            with self.same_source_merge_file.open("a", encoding="utf8") as file:
                file.write(merge_info + "\n")

        if (
            colrev.settings.SameSourceMergePolicy.prevent
            == self.review_manager.settings.dedupe.same_source_merges
        ):
            self.review_manager.logger.warning(
                f"Prevented same-source merge: ({merge_info})"
            )

            with self.prevented_same_source_merge_file.open(
                "a", encoding="utf8"
            ) as file:
                file.write(merge_info + "\n")

    def __is_cross_level_merge(
        self, *, main_record: colrev.record.Record, dupe_record: colrev.record.Record
    ) -> bool:
        is_cross_level_merge_attempt = False
        if main_record.data["ENTRYTYPE"] in ["proceedings"] or dupe_record.data[
            "ENTRYTYPE"
        ] in ["proceedings"]:
            is_cross_level_merge_attempt = True

        if (
            main_record.data["ENTRYTYPE"] == "book"
            and dupe_record.data["ENTRYTYPE"] == "inbook"
        ):
            is_cross_level_merge_attempt = True

        if (
            main_record.data["ENTRYTYPE"] == "inbook"
            and dupe_record.data["ENTRYTYPE"] == "book"
        ):
            is_cross_level_merge_attempt = True

        return is_cross_level_merge_attempt

    def __gids_conflict(
        self, *, main_record: colrev.record.Record, dupe_record: colrev.record.Record
    ) -> bool:
        gid_conflict = False

        if main_record.data.get("doi", "doi-a") != dupe_record.data.get("doi", "doi-b"):
            gid_conflict = True

        return gid_conflict

    def __print_merge_stats(
        self,
        *,
        records: dict,
        duplicate_id_mappings: dict,
        removed_duplicates: list,
        complete_dedupe: bool,
        set_to_md_processed: list,
    ) -> None:
        for record_id, duplicate_ids in duplicate_id_mappings.items():
            if record_id not in records:
                continue
            if (
                colrev.record.RecordState.md_prepared
                == records[record_id]["colrev_status"]
            ):
                if complete_dedupe:
                    self.review_manager.logger.info(
                        f" {colors.GREEN}{record_id} ({','.join(duplicate_ids)})".ljust(
                            46
                        )
                        + f"md_prepared →  md_processed{colors.END}"
                    )
                else:
                    self.review_manager.logger.info(
                        f" {colors.GREEN}{record_id} ({','.join(duplicate_ids)})".ljust(
                            46
                        )
                        + f"md_prepared →  md_prepared{colors.END}"
                    )
        if complete_dedupe:
            for rid in set_to_md_processed:
                self.review_manager.logger.info(
                    f" {colors.GREEN}{rid}".ljust(46)
                    + f"md_prepared →  md_processed{colors.END}"
                )

        self.review_manager.logger.info(
            "Merged duplicates: ".ljust(39) + f"{len(removed_duplicates)} records"
        )

    def apply_merges(
        self,
        *,
        results: list,
        complete_dedupe: bool = False,
        preferred_masterdata_sources: Optional[list] = None,
    ) -> None:
        """Apply automated deduplication decisions

        Level: IDs (not colrev_origins), requiring IDs to be immutable after md_prepared

        record['colrev_status'] can only be set to md_processed after running the
        active-learning classifier and checking whether the record is not part of
        any other duplicate-cluster
        - If the results list does not contain a 'score' value, it is generated
        manually and we cannot set the 'colrev_status' to md_processed
        - If the results list contains a 'score value'

        - complete_dedupe: when not all potential duplicates were considered,
        we cannot set records to md_procssed for non-duplicate decisions

        results : [{"ID1": "...", "ID2": "...", "decision": "duplicate"}]

        """

        # The merging also needs to consider whether IDs are propagated
        # Completeness of comparisons should be ensured by the
        # dedupe clustering routine

        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals

        if not results:
            return

        preferred_masterdata_source_prefixes = []
        if preferred_masterdata_sources:
            preferred_masterdata_source_prefixes = [
                s.get_origin_prefix() for s in preferred_masterdata_sources
            ]

        records = self.review_manager.dataset.load_records_dict()

        removed_duplicates = []
        duplicate_id_mappings = {}
        record_to_merge = self.__get_records_to_merge(records=records, results=results)
        for main_record, dupe_record, dupe in record_to_merge:
            try:
                if self.__is_cross_level_merge(
                    main_record=main_record, dupe_record=dupe_record
                ):
                    self.review_manager.logger.debug(
                        "Prevented cross-level merge: "
                        f"{main_record.data['ID']} - {dupe_record.data['ID']}"
                    )
                    continue

                if self.__gids_conflict(
                    main_record=main_record, dupe_record=dupe_record
                ):
                    self.review_manager.logger.debug(
                        "Prevented merge with conflicting global IDs: "
                        f"{main_record.data['ID']} - {dupe_record.data['ID']}"
                    )
                    continue

                if self.__same_source_merge(
                    main_record=main_record, dupe_record=dupe_record
                ):
                    self.__export_same_source_merge(
                        main_record=main_record,
                        dupe_record=dupe_record,
                    )

                    if (
                        colrev.settings.SameSourceMergePolicy.prevent
                        == self.review_manager.settings.dedupe.same_source_merges
                    ):
                        self.review_manager.logger.debug(
                            "Prevented same-source merge: "
                            f"{main_record.data['ID']} - {dupe_record.data['ID']}"
                        )
                        self.review_manager.logger.info(
                            "To force merge use colrev dedupe --merge "
                            f"{main_record.data['ID']},{dupe_record.data['ID']}"
                        )

                        continue  # with next pair

                    self.review_manager.logger.debug(
                        "Applying same-source merge: "
                        f"{main_record.data['ID']} - {dupe_record.data['ID']}"
                    )

                self.review_manager.logger.debug(
                    f"Merge: {main_record.data['ID']} - {dupe_record.data['ID']}"
                )
                if main_record.data["ID"] not in duplicate_id_mappings:
                    duplicate_id_mappings[main_record.data["ID"]] = [
                        dupe_record.data["ID"]
                    ]
                else:
                    duplicate_id_mappings[main_record.data["ID"]].append(
                        dupe_record.data["ID"]
                    )

                dupe_record.data["MOVED_DUPE_ID"] = main_record.data["ID"]
                main_record.merge(
                    merging_record=dupe_record,
                    default_source="merged",
                    preferred_masterdata_source_prefixes=preferred_masterdata_source_prefixes,
                )
                removed_duplicates.append(dupe_record.data["ID"])

                if "score" in dupe:
                    conf_details = (
                        f"(confidence: {str(round(dupe['score'], 3))})"
                        if "score" in dupe
                        else ""
                    )

                    self.review_manager.logger.debug(
                        f"Removed duplicate{conf_details}: "
                        + f'{main_record.data["ID"]} <- {dupe_record.data["ID"]}'
                    )
            except colrev_exceptions.InvalidMerge:
                continue

        for record in records.values():
            if "MOVED_DUPE_ID" in record:
                del record["MOVED_DUPE_ID"]
        for removed_duplicate in removed_duplicates:
            if removed_duplicate in records:
                del records[removed_duplicate]

        set_to_md_processed = []
        if complete_dedupe:
            # Set remaining records to md_processed (not duplicate) because all records
            # have been considered by dedupe
            for record_dict in records.values():
                if (
                    record_dict["colrev_status"]
                    == colrev.record.RecordState.md_prepared
                ):
                    record = colrev.record.Record(data=record_dict)
                    record.set_status(
                        target_state=colrev.record.RecordState.md_processed
                    )
                    set_to_md_processed.append(record.data["ID"])

        self.__print_merge_stats(
            records=records,
            duplicate_id_mappings=duplicate_id_mappings,
            removed_duplicates=removed_duplicates,
            complete_dedupe=complete_dedupe,
            set_to_md_processed=set_to_md_processed,
        )

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

    def __get_records_to_merge(
        self, *, records: dict, results: list
    ) -> typing.Iterable[tuple]:
        """Resolves multiple/chained duplicates (by following the MOVED_DUPE_ID mark)
        and returns tuples with the primary merge record in the first position."""

        duplicates_to_process = [x for x in results if "duplicate" == x["decision"]]
        for dupe in duplicates_to_process:
            try:
                rec_1 = records[dupe.pop("ID1")]
                rec_2 = records[dupe.pop("ID2")]
            except KeyError:
                print(f"skip {dupe}")
                continue

            # Simple way of implementing the closure
            # cases where the main_record has already been merged into another record
            while "MOVED_DUPE_ID" in rec_1:
                rec_1 = records[rec_1["MOVED_DUPE_ID"]]
            while "MOVED_DUPE_ID" in rec_2:
                rec_2 = records[rec_2["MOVED_DUPE_ID"]]

            if rec_1["ID"] == rec_2["ID"]:
                continue

            main_record_dict, dupe_record_dict = self.__select_primary_merge_record(
                rec_1, rec_2
            )

            main_record = colrev.record.Record(data=main_record_dict)
            dupe_record = colrev.record.Record(data=dupe_record_dict)

            yield (main_record, dupe_record, dupe)

    def __unmerge_current_record_ids_records(self, *, current_record_ids: list) -> dict:
        ids_origins: typing.Dict[str, list] = {rid: [] for rid in current_record_ids}

        for records in self.review_manager.dataset.load_records_from_history():
            for rid in ids_origins:
                ids_origins[rid] = records[rid]["colrev_origin"]
            break

        records = self.review_manager.dataset.load_records_dict()
        for rid in ids_origins:
            del records[rid]

        unmerged, first = False, True
        for recs in self.review_manager.dataset.load_records_from_history():
            if first:
                first = False
                continue
            for rid in list(ids_origins.keys()):
                if rid not in recs:
                    break

                if ids_origins[rid] == recs[rid]:
                    break

                for record in recs.values():
                    if any(
                        orig in ids_origins[rid] for orig in record["colrev_origin"]
                    ):
                        records[record["ID"]] = record
                        unmerged = True
            if unmerged:
                break
        return records

    def __unmerge_previous_id_lists_records(self, *, previous_id_lists: list) -> dict:
        records = self.review_manager.dataset.load_records_dict()
        git_repo = self.review_manager.dataset.get_repo()
        revlist = (
            (
                (
                    commit.tree / str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                ).data_stream.read()
            )
            for commit in git_repo.iter_commits(
                paths=str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
            )
        )

        unmerged = False
        for filecontents in revlist:
            prior_records_dict = self.review_manager.dataset.load_records_dict(
                load_str=filecontents.decode("utf-8")
            )

            for id_list_to_unmerge in previous_id_lists:
                self.review_manager.report_logger.info(
                    f'Undo merge: {",".join(id_list_to_unmerge)}'
                )
                self.review_manager.logger.info(
                    f'Undo merge: {",".join(id_list_to_unmerge)}'
                )

                if all(rec_id in prior_records_dict for rec_id in id_list_to_unmerge):
                    # delete new record,
                    # add previous records (from history) to records
                    records = {
                        k: v for k, v in records.items() if k not in id_list_to_unmerge
                    }

                    for record_dict in prior_records_dict.values():
                        if record_dict["ID"] in id_list_to_unmerge:
                            # add manual_dedupe/non_dupe decision to the records
                            manual_non_duplicates = id_list_to_unmerge.copy()
                            manual_non_duplicates.remove(record_dict["ID"])

                            # The followin may need to be set to the previous state of the
                            # record that was erroneously merged (could be md_prepared)
                            record = colrev.record.Record(data=record_dict)
                            record.set_status(
                                target_state=colrev.record.RecordState.md_processed
                            )
                            records[record_dict["ID"]] = record_dict
                            self.review_manager.logger.info(
                                f'Restored {record_dict["ID"]}'
                            )
                    unmerged = True

                if unmerged:
                    break
            if unmerged:
                break

        if not unmerged:
            self.review_manager.logger.error(
                f"Could not restore {previous_id_lists} - " "please fix manually"
            )

        return records

    def unmerge_records(
        self,
        *,
        current_record_ids: Optional[list] = None,
        previous_id_lists: Optional[list] = None,
    ) -> None:
        """Unmerge duplicate decision of the records, as identified by their ids.

        The current_record_ids identifies the records by their current IDs and
        unmerges their most recent merge in history.

        The previous_id_lists identifies the records by their IDs in the previous commit and
        only considers merges in the previous commit.

        """

        assert not (previous_id_lists and current_record_ids)

        if current_record_ids:
            records = self.__unmerge_current_record_ids_records(
                current_record_ids=current_record_ids
            )

        if previous_id_lists:
            records = self.__unmerge_previous_id_lists_records(
                previous_id_lists=previous_id_lists
            )

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

    def fix_errors(self) -> None:
        """Fix errors as highlighted in the Excel files"""

        # pylint: disable=too-many-branches

        self.review_manager.report_logger.info("Dedupe: fix errors")
        self.review_manager.logger.info("Dedupe: fix errors")

        if self.dupe_file.is_file():
            dupes = pd.read_excel(self.dupe_file)
            dupes.fillna("", inplace=True)
            c_to_correct = dupes.loc[dupes["error"] != "", "cluster_id"].to_list()
            dupes = dupes[dupes["cluster_id"].isin(c_to_correct)]
            previous_ids_to_unmerge = (
                dupes.groupby(["cluster_id"], group_keys=False)["ID"]
                .apply(list)
                .tolist()
            )

            if previous_ids_to_unmerge:
                self.unmerge_records(previous_id_lists=previous_ids_to_unmerge)

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
                    non_dupes.groupby(["cluster_id"], group_keys=False)["ID"]
                    .apply(list)
                    .tolist()
                )
            if self.non_dupe_file_txt.is_file():
                content = self.non_dupe_file_txt.read_text()
                ids_to_merge = [x.split(",") for x in content.splitlines()]
                for id_1, id_2 in ids_to_merge:
                    print(f"{id_1} - {id_2}")

            dedupe_errors = []
            for id_list in ids_to_merge:
                if 2 == len(id_list):
                    dedupe_errors.append(
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
                        dedupe_errors.append(
                            {
                                "ID1": id_list[0],
                                "ID2": idc,
                                "decision": "duplicate",
                            }
                        )
            self.apply_merges(results=dedupe_errors, complete_dedupe=False)

        if self.review_manager.dataset.records_changed():
            self.review_manager.create_commit(
                msg="Validate and correct duplicates",
                manual_author=True,
            )
        if not (
            self.dupe_file.is_file()
            or self.non_dupe_file_xlsx.is_file()
            or self.non_dupe_file_txt.is_file()
        ):
            self.review_manager.logger.error("No file with potential errors found.")

    def get_info(self) -> dict:
        """Get info on cuts (overlap of search sources) and same source merges"""

        records = self.review_manager.dataset.load_records_dict()

        origins = [record["colrev_origin"] for record in records.values()]
        origins = [item.split("/")[0] for sublist in origins for item in sublist]
        origins = list(set(origins))

        same_source_merges = []

        for record in records.values():
            rec_sources = [x.split("/")[0] for x in record["colrev_origin"]]

            duplicated_sources = [
                item for item, count in Counter(rec_sources).items() if count > 1
            ]
            if len(duplicated_sources) > 0:
                all_cases = []
                for duplicated_source in duplicated_sources:
                    cases = [
                        o.split("/")[1]
                        for o in record["colrev_origin"]
                        if duplicated_source in o
                    ]
                    all_cases.append(f"{duplicated_source}: {cases}")
                same_source_merges.append(f"{record['ID']} ({', '.join(all_cases)})")

        info = {
            "same_source_merges": same_source_merges,
        }
        return info

    def merge_records(self, *, merge: str) -> None:
        """Merge two records by ID"""

        merge_ids = merge.split(",")
        results = [{"ID1": merge_ids[0], "ID2": merge_ids[1], "decision": "duplicate"}]
        self.apply_merges(results=results)

    def merge_based_on_global_ids(self, *, apply: bool = False) -> None:
        """Merge records based on global IDs (e.g., doi)"""

        # pylint: disable=too-many-branches

        records = self.review_manager.dataset.load_records_dict()

        global_keys = ["doi", "colrev_id", "pubmedid", "dblp_key", "url"]
        if "colrev_id" in global_keys:
            for record in records.values():
                try:
                    record["colrev_id"] = colrev.record.Record(
                        data=record
                    ).create_colrev_id()
                except colrev_exceptions.NotEnoughDataToIdentifyException:
                    pass

        results = []
        for global_key in global_keys:
            key_dict: typing.Dict[str, list] = {}
            for record in records.values():
                if global_key not in record:
                    continue
                if record[global_key] in key_dict:
                    key_dict[record[global_key]].append(record["ID"])
                else:
                    key_dict[record[global_key]] = [record["ID"]]

            key_dict = {k: v for k, v in key_dict.items() if len(v) > 1}
            for record_ids in key_dict.values():
                for ref_rec_id in range(1, len(record_ids)):
                    results.append(
                        {
                            "ID1": record_ids[0],
                            "ID2": record_ids[ref_rec_id],
                            "decision": "duplicate",
                        }
                    )

        if apply:
            self.review_manager.settings.dedupe.same_source_merges = (
                colrev.settings.SameSourceMergePolicy.warn
            )
            self.apply_merges(results=results)
            self.review_manager.create_commit(
                msg="Merge records (identical global IDs)"
            )

        elif results:
            print()
            self.review_manager.logger.info("Found records with identical global-ids:")
            print(results)
            self.review_manager.logger.info(
                f"{colors.ORANGE}To merge records with identical global-ids, "
                f"run colrev merge -gid{colors.END}"
            )
            print()

        else:
            print()

    def main(self) -> None:
        """Dedupe records (main entrypoint)"""

        self.review_manager.logger.info("Dedupe")
        self.review_manager.logger.info(
            "Identifies duplicate records and merges them (keeping traces to their origins)."
        )
        self.review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/dedupe.html"
        )

        if not self.review_manager.high_level_operation:
            print()

        self.merge_based_on_global_ids(apply=True)

        package_manager = self.review_manager.get_package_manager()
        for (
            dedupe_package_endpoint
        ) in self.review_manager.settings.dedupe.dedupe_package_endpoints:
            # Note : load package/script at this point because the same script
            # may run with different parameters
            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.dedupe,
                selected_packages=[dedupe_package_endpoint],
                operation=self,
                only_ci_supported=self.review_manager.in_ci_environment(),
            )
            if dedupe_package_endpoint["endpoint"] not in endpoint_dict:
                self.review_manager.logger.info(
                    f'Skip {dedupe_package_endpoint["endpoint"]} (not available)'
                )
                if self.review_manager.in_ci_environment():
                    raise colrev_exceptions.ServiceNotAvailableException(
                        dep="colrev dedupe",
                        detailed_trace="dedupe not available in ci environment",
                    )
                raise colrev_exceptions.ServiceNotAvailableException(
                    dep="colrev dedupe", detailed_trace="dedupe not available"
                )

            endpoint = endpoint_dict[dedupe_package_endpoint["endpoint"]]

            endpoint.run_dedupe(self)  # type: ignore
            if not self.review_manager.high_level_operation:
                print()

        dedupe_commit_id = self.review_manager.dataset.get_repo().head.commit.hexsha
        self.review_manager.logger.info("To validate the changes, use")

        self.review_manager.logger.info(
            f"{colors.ORANGE}colrev validate {dedupe_commit_id}{colors.END}"
        )
        print()

        self.review_manager.logger.info(
            f"{colors.GREEN}Completed dedupe operation{colors.END}"
        )

        if not self.review_manager.settings.prescreen.prescreen_package_endpoints:
            self.review_manager.logger.info("Skipping prescreen/including all records")
            records = self.review_manager.dataset.load_records_dict()
            for record_dict in records.values():
                record = colrev.record.Record(data=record_dict)
                if (
                    colrev.record.RecordState.md_processed
                    == record.data["colrev_status"]
                ):
                    record.set_status(
                        target_state=colrev.record.RecordState.rev_prescreen_included
                    )

            self.review_manager.dataset.save_records_dict(records=records)
            self.review_manager.dataset.add_record_changes()
            self.review_manager.create_commit(msg="Skip prescreen/include all")

        if self.review_manager.in_ci_environment():
            print("\n\n")


if __name__ == "__main__":
    pass
