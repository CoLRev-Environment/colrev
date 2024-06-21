#! /usr/bin/env python
"""CoLRev dedupe operation: identify and merge duplicate records."""
from __future__ import annotations

import string
import typing
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd
from bib_dedupe.bib_dedupe import prep

import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.record.record
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState


class Dedupe(colrev.process.operation.Operation):
    """Deduplicate records (entity resolution)"""

    NON_DUPLICATE_FILE_XLSX = Path("non_duplicates_to_validate.xlsx")
    NON_DUPLICATE_FILE_TXT = Path("non_duplicates_to_validate.txt")
    DUPLICATES_TO_VALIDATE = Path("duplicates_to_validate.xlsx")
    SAME_SOURCE_MERGE_FILE = Path("same_source_merges.txt")
    PREVENTED_SAME_SOURCE_MERGE_FILE = Path("prevented_same_source_merges.txt")

    debug = False
    type = OperationsType.dedupe

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=notify_state_transition_operation,
        )
        self.dedupe_dir = self.review_manager.paths.dedupe
        self.non_dupe_file_xlsx = self.dedupe_dir / self.NON_DUPLICATE_FILE_XLSX
        self.non_dupe_file_txt = self.dedupe_dir / self.NON_DUPLICATE_FILE_TXT
        self.dupe_file = self.dedupe_dir / self.DUPLICATES_TO_VALIDATE

        self.same_source_merge_file = self.dedupe_dir / self.SAME_SOURCE_MERGE_FILE
        self.prevented_same_source_merge_file = (
            self.dedupe_dir / self.PREVENTED_SAME_SOURCE_MERGE_FILE
        )
        self.dedupe_dir.mkdir(exist_ok=True, parents=True)

    @classmethod
    def _dfs(cls, node: str, graph: dict, visited: dict, component: list) -> None:
        visited[node] = True
        component.append(node)
        for neighbor in graph[node]:
            if not visited[neighbor]:
                cls._dfs(neighbor, graph, visited, component)

    @classmethod
    def connected_components(cls, id_sets: list) -> list:
        """
        Find the connected components in a graph.

        Args:
            id_sets (list): A list of id sets.

        Returns:
            list: A list of connected components.
        """
        graph = defaultdict(list)

        # Create an adjacency list
        for origin_set in id_sets:
            for combination in combinations(origin_set, 2):
                graph[combination[0]].append(combination[1])
                graph[combination[1]].append(combination[0])

        visited = {node: False for node in graph}
        components = []

        for node in graph:
            if not visited[node]:
                component: typing.List[str] = []
                cls._dfs(node, graph, visited, component)
                components.append(sorted(component))

        return components

    @classmethod
    def get_records_for_dedupe(
        cls, *, records_df: pd.DataFrame, verbosity_level: int = 0
    ) -> pd.DataFrame:
        """Get (pre-processed) records for dedupe"""
        return prep(records_df=records_df, verbosity_level=verbosity_level)

    def _select_primary_merge_record(self, rec_1: dict, rec_2: dict) -> list:
        # pylint: disable=too-many-branches

        # Heuristic

        # 1. if both records are prepared (or the same status),
        # merge into the record with the "lower" colrev_id
        if rec_1[Fields.STATUS] == rec_2[Fields.STATUS]:
            if rec_1[Fields.ID][-1].isdigit() and not rec_2[Fields.ID][-1].isdigit():
                main_record = rec_1
                dupe_record = rec_2
            elif (
                not rec_1[Fields.ID][-1].isdigit()
                and not rec_2[Fields.ID][-1].isdigit()
            ):
                # Last characters are letters in both records
                # Select the one that's first in the alphabet
                try:
                    pos_rec_1_suffix = string.ascii_lowercase.index(
                        rec_1[Fields.ID][-1]
                    )
                except ValueError:
                    pos_rec_1_suffix = -1
                try:
                    pos_rec_2_suffix = string.ascii_lowercase.index(
                        rec_2[Fields.ID][-1]
                    )
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
        elif rec_1[Fields.STATUS] == RecordState.md_prepared:
            main_record = rec_2
            dupe_record = rec_1
        elif rec_2[Fields.STATUS] == RecordState.md_prepared:
            main_record = rec_1
            dupe_record = rec_2

        # 3. If a record is md_processed, use the other record as the dupe record
        # -> during the fix_errors procedure, records are in md_processed
        # and beyond.
        elif rec_1[Fields.STATUS] == RecordState.md_processed:
            main_record = rec_1
            dupe_record = rec_2
        elif rec_2[Fields.STATUS] == RecordState.md_processed:
            main_record = rec_2
            dupe_record = rec_1

        # 4. Merge into curated record (otherwise)
        else:
            if colrev.record.record.Record(rec_2).masterdata_is_curated():
                main_record = rec_2
                dupe_record = rec_1
            else:
                main_record = rec_1
                dupe_record = rec_2

        return [main_record, dupe_record]

    def _same_source_merge(
        self,
        *,
        main_record: colrev.record.record.Record,
        dupe_record: colrev.record.record.Record,
    ) -> bool:
        main_rec_sources = [x.split("/")[0] for x in main_record.data[Fields.ORIGIN]]
        dupe_rec_sources = [x.split("/")[0] for x in dupe_record.data[Fields.ORIGIN]]
        same_sources = set(main_rec_sources).intersection(set(dupe_rec_sources))

        if len(same_sources) == 0:
            return False

        # don't raise unproblematic same-source merges
        # if same_sources start with md_... AND have same IDs: no same-source merge.
        if all(x.startswith("md_") for x in same_sources):
            main_rec_same_source_origins = [
                x
                for x in main_record.data[Fields.ORIGIN]
                if x.split("/")[0] in same_sources
            ]
            dupe_rec_same_source_origins = [
                x
                for x in dupe_record.data[Fields.ORIGIN]
                if x.split("/")[0] in same_sources
            ]
            if set(main_rec_same_source_origins) == set(dupe_rec_same_source_origins):
                return False
            return True
        return True

    def _notify_on_merge(
        self,
        *,
        main_record: colrev.record.record.Record,
        dupe_record: colrev.record.record.Record,
    ) -> None:
        merge_info = main_record.data[Fields.ID] + " - " + dupe_record.data[Fields.ID]
        if not self._same_source_merge(
            main_record=main_record, dupe_record=dupe_record
        ):
            self.review_manager.logger.info(
                f" merge {main_record.data[Fields.ID]} - {dupe_record.data[Fields.ID]}"
            )
            return

        self.review_manager.logger.warning(
            f"{Colors.ORANGE}"
            "Apply same source merge "
            f"{Colors.END} "
            f"{merge_info}\n"
            f"  {main_record.format_bib_style()}\n"
            f"  {dupe_record.format_bib_style()}\n"
            f"  {main_record.data.get(Fields.ORIGIN, ['ERROR'])} x "
            f"{dupe_record.data.get(Fields.ORIGIN, ['ERROR'])}\n"
        )

    def _is_cross_level_merge(
        self,
        *,
        main_record: colrev.record.record.Record,
        dupe_record: colrev.record.record.Record,
    ) -> bool:
        is_cross_level_merge_attempt = False
        if main_record.data[Fields.ENTRYTYPE] in [
            ENTRYTYPES.PROCEEDINGS
        ] or dupe_record.data[Fields.ENTRYTYPE] in [ENTRYTYPES.PROCEEDINGS]:
            is_cross_level_merge_attempt = True

        if (
            main_record.data[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK
            and dupe_record.data[Fields.ENTRYTYPE] == ENTRYTYPES.INBOOK
        ):
            is_cross_level_merge_attempt = True

        if (
            main_record.data[Fields.ENTRYTYPE] == ENTRYTYPES.INBOOK
            and dupe_record.data[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK
        ):
            is_cross_level_merge_attempt = True

        return is_cross_level_merge_attempt

    # pylint: disable=too-many-arguments
    def _print_merge_stats(
        self,
        *,
        records: dict,
        duplicate_id_mappings: dict,
        removed_duplicates: list,
        complete_dedupe: bool,
        set_to_md_processed: list,
    ) -> None:
        print()
        self.review_manager.logger.info("Summary:")
        for record_id, duplicate_ids in duplicate_id_mappings.items():
            duplicate_ids = [x.replace(record_id, "-") for x in duplicate_ids]
            if record_id not in records:
                continue
            if RecordState.md_prepared == records[record_id][Fields.STATUS]:
                if complete_dedupe:
                    self.review_manager.logger.info(
                        f" {Colors.GREEN}{record_id} ({'|'.join(duplicate_ids)}) ".ljust(
                            46
                        )
                        + f"md_prepared →  md_processed{Colors.END}"
                    )
                else:
                    self.review_manager.logger.info(
                        f" {Colors.GREEN}{record_id} ({'|'.join(duplicate_ids)}) ".ljust(
                            46
                        )
                        + f"md_prepared →  md_prepared{Colors.END}"
                    )
        if complete_dedupe:
            for rid in set_to_md_processed:
                self.review_manager.logger.info(
                    f" {Colors.GREEN}{rid}".ljust(46)
                    + f"md_prepared →  md_processed{Colors.END}"
                )

        self.review_manager.logger.info(
            "Merged duplicates: ".ljust(39) + f"{len(removed_duplicates)} records"
        )

    def _apply_records_merges(
        self, *, records: dict, removed_duplicates: list, complete_dedupe: bool
    ) -> list:
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
                if record_dict[Fields.STATUS] == RecordState.md_prepared:
                    record = colrev.record.record.Record(record_dict)
                    record.set_status(RecordState.md_processed)
                    set_to_md_processed.append(record.data[Fields.ID])

        self.review_manager.dataset.save_records_dict(records)
        return set_to_md_processed

    def _skip_merge_condition(
        self,
        *,
        main_record: colrev.record.record.Record,
        dupe_record: colrev.record.record.Record,
    ) -> bool:
        if self.review_manager.force_mode:
            return False
        if self._is_cross_level_merge(main_record=main_record, dupe_record=dupe_record):
            self.review_manager.logger.info(
                "Prevented cross-level merge: "
                f"{main_record.data[Fields.ID]} - {dupe_record.data[Fields.ID]}"
            )
            return True

        # if (
        #     self._same_source_merge(main_record=main_record, dupe_record=dupe_record)
        #     and self.policy == colrev.settings.SameSourceMergePolicy.prevent
        # ):
        #     self.review_manager.logger.info(
        #         "Prevented same-source merge: "
        #         f"{main_record.data[Fields.ID]} - {dupe_record.data[Fields.ID]}"
        #     )
        #     return True

        return False

    def _update_duplicate_id_mappings(
        self,
        *,
        duplicate_id_mappings: dict,
        main_record: colrev.record.record.Record,
        dupe_record: colrev.record.record.Record,
    ) -> None:
        if main_record.data[Fields.ID] not in duplicate_id_mappings:
            duplicate_id_mappings[main_record.data[Fields.ID]] = [
                dupe_record.data[Fields.ID]
            ]
        else:
            duplicate_id_mappings[main_record.data[Fields.ID]].append(
                dupe_record.data[Fields.ID]
            )

    def apply_merges(
        self,
        *,
        id_sets: list,
        complete_dedupe: bool = False,
        preferred_masterdata_sources: typing.Optional[list] = None,
    ) -> None:
        """Apply deduplication decisions

        id_sets : [[ID_1, ID_2, ID_3], ...]

        - complete_dedupe: when not all potential duplicates were considered,
        we cannot set records to md_procssed for non-duplicate decisions
        """

        preferred_masterdata_source_prefixes = []
        if preferred_masterdata_sources:
            preferred_masterdata_source_prefixes = [
                s.get_origin_prefix() for s in preferred_masterdata_sources
            ]

        records = self.review_manager.dataset.load_records_dict()
        non_existing_ids = [
            ID
            for ID in [id for id_set in id_sets for id in id_set]
            if ID not in records
        ]
        if non_existing_ids:
            print(f"Non-existing IDs: {non_existing_ids}")
            print(f"Records IDs: {records.keys()}")
        assert not non_existing_ids, "Not all IDs from id_sets are present in records"

        # Notify users about items with only one unique ID
        for id_set in id_sets:
            if len(set(id_set)) == 1:
                self.review_manager.logger.info(
                    f"Skipping merge for identical IDs: {id_set[0]}"
                )
        # Drop cases where IDs are identical
        id_sets = [id_set for id_set in id_sets if len(set(id_set)) != 1]

        removed_duplicates = []
        duplicate_id_mappings: typing.Dict[str, list] = {}
        for main_record, dupe_record in self._get_records_to_merge(
            records=records, id_sets=id_sets
        ):
            if self._skip_merge_condition(
                main_record=main_record, dupe_record=dupe_record
            ):
                continue

            self._notify_on_merge(
                main_record=main_record,
                dupe_record=dupe_record,
            )

            self._update_duplicate_id_mappings(
                duplicate_id_mappings=duplicate_id_mappings,
                main_record=main_record,
                dupe_record=dupe_record,
            )
            dupe_record.data["MOVED_DUPE_ID"] = main_record.data[Fields.ID]
            main_record.merge(
                dupe_record,
                default_source="merged",
                preferred_masterdata_source_prefixes=preferred_masterdata_source_prefixes,
            )
            removed_duplicates.append(dupe_record.data[Fields.ID])

        set_to_md_processed = self._apply_records_merges(
            records=records,
            removed_duplicates=removed_duplicates,
            complete_dedupe=complete_dedupe,
        )

        self._print_merge_stats(
            records=records,
            duplicate_id_mappings=duplicate_id_mappings,
            removed_duplicates=removed_duplicates,
            complete_dedupe=complete_dedupe,
            set_to_md_processed=set_to_md_processed,
        )

    def _get_records_to_merge(
        self, *, records: dict, id_sets: list
    ) -> typing.Iterable[tuple]:
        """Resolves multiple/chained duplicates (by following the MOVED_DUPE_ID mark)
        and returns tuples with the primary merge record in the first position."""

        for id_set in id_sets:
            recs_to_merge = [r for r in records.values() if r[Fields.ID] in id_set]

            # Simple way of implementing the closure
            # cases where the main_record has already been merged into another record
            for ind, rec_to_merge in enumerate(recs_to_merge):
                cur_rec = rec_to_merge
                while "MOVED_DUPE_ID" in cur_rec:
                    cur_rec = records[cur_rec["MOVED_DUPE_ID"]]
                recs_to_merge[ind] = cur_rec

            if all(recs_to_merge[0][Fields.ID] == r[Fields.ID] for r in recs_to_merge):
                continue

            for rec_1, rec_2 in combinations(recs_to_merge, 2):
                main_record_dict, dupe_record_dict = self._select_primary_merge_record(
                    rec_1, rec_2
                )

                main_record = colrev.record.record.Record(main_record_dict)
                dupe_record = colrev.record.record.Record(dupe_record_dict)

                yield (main_record, dupe_record)

    def _get_origins_for_current_ids(self, current_record_ids: list) -> dict:
        """
        For each record ID, get the origins from the most recent history entry.
        """

        ids_origins: typing.Dict[str, typing.List[str]] = {
            rid: [] for rid in current_record_ids
        }
        # history = next(self.review_manager.dataset.load_records_from_history(), None)
        # if history:
        #     for rid in ids_origins:
        #         ids_origins[rid] = history.get(rid, {}).get(Fields.ORIGIN, [])

        records = self.review_manager.dataset.load_records_dict()
        for rid in ids_origins:
            ids_origins[rid] = records.get(rid, {}).get(Fields.ORIGIN, [])
            if ids_origins[rid] == []:
                raise colrev_exceptions.RecordNotFoundException(
                    f"Did not find record with ID {rid} for unmerge"
                )

        return ids_origins

    def _remove_merged_records(self, records: dict, ids_origins: dict) -> None:
        """
        Remove records that have been merged from the records dictionary.
        These records are identified by their current IDs.
        """
        for rid in ids_origins:
            records.pop(rid, None)

    def _revert_merge_for_records(
        self, unmerged_records: dict, ids_origins: dict
    ) -> dict:
        """
        Attempt to revert the merge operation for each record based on its origins.
        """

        for hist_recs in self.review_manager.dataset.load_records_from_history():
            for rid in list(ids_origins.keys()):
                origins = ids_origins[rid]

                unmerged_rids = []

                for hist_rec in hist_recs.values():
                    if not set(hist_rec.get(Fields.ORIGIN, [])).intersection(
                        set(origins)
                    ):
                        continue

                    # skip if hist_recs still contains the merged records (identical origin set)
                    # ie., need to consider older commits
                    if origins == hist_recs[rid].get(Fields.ORIGIN, []):
                        continue
                    if any(orig in origins for orig in hist_rec.get(Fields.ORIGIN, [])):
                        assert hist_rec[Fields.ID] not in unmerged_records
                        hist_rec.update({Fields.STATUS: RecordState.md_processed})
                        self.review_manager.logger.info(
                            f"add historical record: {hist_rec[Fields.ID]}"
                        )
                        unmerged_records[hist_rec[Fields.ID]] = hist_rec
                        unmerged_rids.append(rid)

                for unmerged_rid in set(unmerged_rids):
                    ids_origins.pop(unmerged_rid)

            # Stop if all unmerged records were restored
            if not ids_origins:
                break

        return unmerged_records

    def unmerge_records(
        self,
        *,
        current_record_ids: list,
    ) -> None:
        """Unmerge duplicate decision of the records, as identified by their ids.

        The current_record_ids identifies the records by their current IDs and
        unmerges their most recent merge in history.

        """
        # Map each current record ID to its origins for easy lookup of historical records.
        ids_origins = self._get_origins_for_current_ids(current_record_ids)
        print(ids_origins)

        # Load the current state of all records.
        records = self.review_manager.dataset.load_records_dict()

        # Remove the merged records from the current state.
        self._remove_merged_records(records, ids_origins)
        print(f"After removal: {records.keys()}")

        # Attempt to revert the merge operation for each record.
        records = self._revert_merge_for_records(records, ids_origins)
        print(f"After revert: {records.keys()}")

        self.review_manager.dataset.save_records_dict(records)

    def fix_errors(self, *, false_positives: list, false_negatives: list) -> None:
        """Fix lists of errors"""

        self.unmerge_records(current_record_ids=false_positives)
        self.apply_merges(id_sets=false_negatives, complete_dedupe=False)

        if self.review_manager.dataset.records_changed():
            self.review_manager.dataset.create_commit(
                msg="Validate and correct duplicates",
                manual_author=True,
            )

    def get_info(self) -> dict:
        """Get info on cuts (overlap of search sources) and same source merges"""

        # same_source_merges: typing.Any = []
        # source_overlaps: typing.Any = []
        # info = {
        #     "same_source_merges": same_source_merges,
        #     "source_overlaps": source_overlaps,
        # }
        # return info
        raise NotImplementedError

    def merge_records(self, *, merge: list) -> None:
        """Merge records by ID sets"""

        self.apply_merges(id_sets=merge)

    def merge_based_on_global_ids(self, *, apply: bool = False) -> None:
        """Merge records based on global IDs (e.g., doi)"""

        # pylint: disable=too-many-branches

        self.review_manager.logger.info(
            "Dedupe operation [merge based on identical global_ids]"
        )

        records = self.review_manager.dataset.load_records_dict()

        global_keys = [
            Fields.DOI,
            Fields.COLREV_ID,
            Fields.PUBMED_ID,
            Fields.DBLP_KEY,
            Fields.URL,
        ]
        if Fields.COLREV_ID in global_keys:
            for record in records.values():
                try:
                    record[Fields.COLREV_ID] = colrev.record.record.Record(
                        data=record
                    ).get_colrev_id()
                except colrev_exceptions.NotEnoughDataToIdentifyException:
                    pass

        id_sets = []
        for global_key in global_keys:
            global_key_dict: typing.Dict[str, list] = {}
            for record in records.values():
                if global_key not in record:
                    continue
                if record[global_key] in global_key_dict:
                    global_key_dict[record[global_key]].append(record[Fields.ID])
                else:
                    global_key_dict[record[global_key]] = [record[Fields.ID]]

            global_key_duplicates = [v for v in global_key_dict.values() if len(v) > 1]
            for duplicate in global_key_duplicates:
                id_sets.extend(list(combinations(duplicate, 2)))

        if apply:
            self.apply_merges(id_sets=id_sets)
            self.review_manager.dataset.create_commit(
                msg="Merge records (identical global IDs)"
            )

        elif id_sets:
            print()
            self.review_manager.logger.info("Found records with identical global-ids:")
            self.review_manager.logger.info(
                f"{Colors.ORANGE}To merge records with identical global-ids, "
                f"run colrev merge -gid{Colors.END}"
            )
            print()

        else:
            print()

    @colrev.process.operation.Operation.decorate()
    def main(self, *, debug: bool = False) -> None:
        """Dedupe records (main entrypoint)"""

        self.review_manager.logger.info("Dedupe")
        self.review_manager.logger.info(
            "Identifies duplicate records and merges them (keeping traces to their origins)."
        )
        self.review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/dedupe.html"
        )
        self.debug = debug

        if not self.review_manager.high_level_operation:
            print()

        package_manager = self.review_manager.get_package_manager()
        for (
            dedupe_package_endpoint
        ) in self.review_manager.settings.dedupe.dedupe_package_endpoints:
            # Note : load package/script at this point because the same script
            # may run with different parameters

            dedupe_class = package_manager.get_package_endpoint_class(
                package_type=EndpointType.dedupe,
                package_identifier=dedupe_package_endpoint["endpoint"],
            )
            endpoint = dedupe_class(
                dedupe_operation=self, settings=dedupe_package_endpoint
            )

            endpoint.run_dedupe()  # type: ignore
            if not self.review_manager.high_level_operation:
                print()

        dedupe_commit_id = self.review_manager.dataset.get_repo().head.commit.hexsha
        self.review_manager.logger.info("To validate the changes, use")

        self.review_manager.logger.info(
            f"{Colors.ORANGE}colrev validate {dedupe_commit_id}{Colors.END}"
        )
        print()

        self.review_manager.logger.info(
            f"{Colors.GREEN}Completed dedupe operation{Colors.END}"
        )

        if not self.review_manager.settings.prescreen.prescreen_package_endpoints:
            self.review_manager.logger.info("Skipping prescreen/including all records")
            records = self.review_manager.dataset.load_records_dict()
            for record_dict in records.values():
                record = colrev.record.record.Record(record_dict)
                if RecordState.md_processed == record.data[Fields.STATUS]:
                    record.set_status(RecordState.rev_prescreen_included)

            self.review_manager.dataset.save_records_dict(records)
            self.review_manager.dataset.create_commit(msg="Skip prescreen/include all")
