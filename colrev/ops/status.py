#! /usr/bin/env python3
"""CoLRev status operation: Display the project status."""
from __future__ import annotations

import csv
import io
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

import colrev.env.utils
import colrev.operation
import colrev.record
import colrev.ui_cli.cli_colors as colrev_colors


class Status(colrev.operation.Operation):
    """Determine the status of the project"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
        )

    def get_analytics(self) -> dict:
        """Get status analytics"""

        analytics_dict = {}
        git_repo = self.review_manager.dataset.get_repo()

        revlist = list(
            (
                commit.hexsha,
                commit.author.name,
                commit.committed_date,
                (commit.tree / "status.yaml").data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths="status.yaml")
        )
        for ind, (commit_id, commit_author, committed_date, filecontents) in enumerate(
            revlist
        ):
            try:
                var_t = io.StringIO(filecontents.decode("utf-8"))

                # TBD: we could simply include the whole status.yaml
                # (to create a general-purpose status analyzer)
                # -> flatten nested structures (e.g., overall/currently)
                # -> integrate with get_status (current data) -
                # and get_prior? (levels: aggregated_statistics vs. record-level?)

                data_loaded = yaml.safe_load(var_t)
                analytics_dict[len(revlist) - ind] = {
                    "commit_id": commit_id,
                    "commit_author": commit_author,
                    "committed_date": committed_date,
                    "search": data_loaded["colrev_status"]["overall"]["md_retrieved"],
                    "included": data_loaded["colrev_status"]["overall"]["rev_included"],
                }
            except (IndexError, KeyError):
                pass

        keys = list(analytics_dict.values())[0].keys()

        with open("analytics.csv", "w", newline="", encoding="utf8") as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(reversed(analytics_dict.values()))

        return analytics_dict

    def get_review_status_report(
        self, *, records: Optional[dict] = None, colors: bool = True
    ) -> str:
        """Get the review status report"""

        status_stats = self.review_manager.get_status_stats(records=records)

        template = colrev.env.utils.get_template(
            template_path="template/ops/status.txt"
        )

        if colors:
            content = template.render(status_stats=status_stats, colors=colrev_colors)
        else:
            content = template.render(status_stats=status_stats, colors=None)

        return content


@dataclass
class StatusStats:
    """Data class for status statistics"""

    # pylint: disable=too-many-instance-attributes
    atomic_steps: int
    nr_curated_records: int
    currently: StatusStatsCurrently
    overall: StatusStatsOverall
    completed_atomic_steps: int
    completeness_condition: bool

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        records: Optional[dict] = None,
    ) -> None:
        self.review_manager = review_manager
        colrev.operation.CheckOperation(review_manager=review_manager)

        if records:
            self.records = records
        else:
            self.records = self.review_manager.dataset.load_records_dict()

        self.status_list = [x["colrev_status"] for x in self.records.values()]
        self.screening_criteria = [
            x["screening_criteria"]
            for x in self.records.values()
            if x.get("screening_criteria", "") not in ["", "NA"]
        ]

        self.md_duplicates_removed = 0
        for item in self.records.values():
            self.md_duplicates_removed += (
                len([o for o in item["colrev_origin"] if not o.startswith("md_")]) - 1
            )

        origin_list = [x["colrev_origin"] for x in self.records.values()]
        self.record_links = 0
        for origin in origin_list:
            self.record_links += len([o for o in origin if not o.startswith("md_")])

        criteria = list(review_manager.settings.screen.criteria.keys())
        self.screening_statistics = {crit: 0 for crit in criteria}
        for screening_case in self.screening_criteria:
            for criterion in screening_case.split(";"):
                criterion_name, decision = criterion.split("=")
                if decision == "out":
                    self.screening_statistics[criterion_name] += 1

        self.currently = self.StatusStatsCurrently(status_stats=self)
        self.overall = self.StatusStatsOverall(status_stats=self)

        self.completed_atomic_steps = 0
        self.nr_incomplete = 0

        self.__overall_stats_backward_calculation()

        self.currently.non_processed = (
            self.currently.md_imported
            + self.currently.md_retrieved
            + self.currently.md_needs_manual_preparation
            + self.currently.md_prepared
        )

        self.currently.md_retrieved = self.overall.md_retrieved - self.record_links

        self.completeness_condition = (
            (0 == self.nr_incomplete)
            and (0 == self.currently.md_retrieved)
            and self.overall.md_retrieved > 0
        )

        self.currently.exclusion = self.screening_statistics

        self.overall.rev_screen = self.overall.pdf_prepared

        self.overall.rev_prescreen = self.overall.md_processed
        self.currently.pdf_needs_retrieval = self.currently.rev_prescreen_included

        colrev_masterdata_items = [
            x["colrev_masterdata_provenance"]
            for x in self.records.values()
            if "colrev_masterdata_provenance" in x
        ]

        self.nr_curated_records = len(
            [x for x in colrev_masterdata_items if "CURATED" in x]
        )
        if review_manager.settings.is_curated_masterdata_repo():
            self.nr_curated_records = self.overall.md_processed

        self.atomic_steps = (
            # initially, all records have to pass 8 operations
            8 * self.overall.md_retrieved
            # for removed duplicates, 5 operations are no longer needed
            - 5 * self.currently.md_duplicates_removed
            # for rev_prescreen_excluded, 4 operations are no longer needed
            - 4 * self.currently.rev_prescreen_excluded
            - 3 * self.currently.pdf_not_available
            - self.currently.rev_excluded
        )

        self.perc_curated = 0
        denominator = (
            self.overall.md_processed
            + self.currently.md_prepared
            + self.currently.md_needs_manual_preparation
            + self.currently.md_imported
        )

        if denominator > 0:
            self.perc_curated = int((self.nr_curated_records / (denominator)) * 100)

    def __overall_stats_backward_calculation(self) -> None:
        """Calculate the state_x overall stats (based on backward calculation)"""
        # self.review_manager.logger.debug(
        #     "Set overall colrev_status statistics (going backwards)"
        # )
        visited_states = []
        current_state = colrev.record.RecordState.rev_synthesized  # start with the last
        atomic_step_number = 0
        while True:
            # self.review_manager.logger.debug(
            #     "current_state: %s with %s",
            #     current_state,
            #     getattr(self.overall, str(current_state)),
            # )
            if colrev.record.RecordState.md_prepared == current_state:
                overall_md_prepared = (
                    getattr(self.overall, str(current_state))
                    + self.md_duplicates_removed
                )
                getattr(self.overall, str(current_state), overall_md_prepared)

            states_to_consider = [current_state]
            predecessors: list[dict[str, typing.Any]] = [
                {
                    "trigger": "init",
                    "source": colrev.record.RecordState.md_imported,
                    "dest": colrev.record.RecordState.md_imported,
                }
            ]
            # Go backward through the process model
            predecessor = None
            while predecessors:
                predecessors = [
                    t
                    for t in colrev.record.RecordStateModel.transitions
                    if t["source"] in states_to_consider
                    and t["dest"] not in visited_states
                ]
                for predecessor in predecessors:
                    # self.review_manager.logger.debug(
                    #     " add %s from %s (predecessor transition: %s)",
                    #     getattr(self.overall, str(predecessor["dest"])),
                    #     str(predecessor["dest"]),
                    #     predecessor["trigger"],
                    # )
                    setattr(
                        self.overall,
                        str(current_state),
                        (
                            getattr(self.overall, str(current_state))
                            + getattr(self.overall, str(predecessor["dest"]))
                        ),
                    )
                    visited_states.append(predecessor["dest"])
                    if predecessor["dest"] not in states_to_consider:
                        states_to_consider.append(predecessor["dest"])
                if len(predecessors) > 0:
                    if predecessors[0]["trigger"] != "init":
                        # ignore _man versions to avoid double-counting:
                        if "_man" not in predecessors[0]["trigger"]:
                            self.completed_atomic_steps += getattr(
                                self.overall, str(predecessor["dest"])
                            )
                        # Note : load is not a predecessor so we need to
                        # correct for a missing step (same number like prep)
                        if predecessors[0]["trigger"] == "prep":
                            self.completed_atomic_steps += getattr(
                                self.overall, str(predecessor["dest"])
                            )

            atomic_step_number += 1
            # Note : the following does not consider multiple parallel steps.
            for trans_for_completeness in [
                t
                for t in colrev.record.RecordStateModel.transitions
                if current_state == t["dest"]
            ]:
                self.nr_incomplete += getattr(
                    self.currently, str(trans_for_completeness["source"])
                )

            t_list = [
                t
                for t in colrev.record.RecordStateModel.transitions
                if current_state == t["dest"]
            ]
            transition: dict = t_list.pop()
            if current_state == colrev.record.RecordState.md_imported:
                break
            current_state = transition["source"]  # go a step back
            self.currently.non_completed += getattr(self.currently, str(current_state))

    def get_active_metadata_operation_info(self) -> str:
        """Get active metadata operation info (convenience function for status printing)"""
        infos = []
        if self.currently.md_retrieved > 0:
            infos.append(f"{self.currently.md_retrieved} to load")
        if self.currently.md_imported > 0:
            infos.append(f"{self.currently.md_imported} to prepare")
        if self.currently.md_needs_manual_preparation > 0:
            infos.append(
                f"{self.currently.md_needs_manual_preparation} to prepare manually"
            )
        if self.currently.md_prepared > 0:
            infos.append(f"{self.currently.md_prepared} to deduplicate")
        return ", ".join(infos)

    def get_active_pdf_operation_info(self) -> str:
        """Get active PDF operation info (convenience function for status printing)"""
        infos = []
        if self.currently.rev_prescreen_included > 0:
            infos.append(f"{self.currently.rev_prescreen_included} to retrieve")
        if self.currently.pdf_needs_manual_retrieval > 0:
            infos.append(
                f"{self.currently.pdf_needs_manual_retrieval} to retrieve manually"
            )
        if self.currently.pdf_imported > 0:
            infos.append(f"{self.currently.pdf_imported} to prepare")
        if self.currently.pdf_needs_manual_preparation > 0:
            infos.append(
                f"{self.currently.pdf_needs_manual_preparation} to prepare manually"
            )
        return ", ".join(infos)

    def get_transitioned_records(
        self, current_origin_states_dict: dict
    ) -> list[typing.Dict]:
        """Get the transitioned records"""

        committed_origin_states_dict = (
            self.review_manager.dataset.get_committed_origin_state_dict()
        )
        transitioned_records = []
        for (
            committed_origin,
            committed_colrev_status,
        ) in committed_origin_states_dict.items():
            transitioned_record = {
                "origin": committed_origin,
                "source": committed_colrev_status,
                "dest": current_origin_states_dict.get(
                    committed_origin, "no_source_state"
                ),
            }

            operations_type = [
                x["trigger"]
                for x in colrev.record.RecordStateModel.transitions
                if x["source"] == transitioned_record["source"]
                and x["dest"] == transitioned_record["dest"]
            ]
            if (
                len(operations_type) == 0
                and transitioned_record["source"] != transitioned_record["dest"]
            ):
                transitioned_record["operations_type"] = "invalid_transition"

            if len(operations_type) > 0:
                transitioned_record["operations_type"] = operations_type[0]
                transitioned_records.append(transitioned_record)

        return transitioned_records

    def get_priority_operations(self, *, current_origin_states_dict: dict) -> list:
        """Get the priority operations"""

        # get "earliest" states (going backward)
        earliest_state = []
        search_states = [colrev.record.RecordState.rev_synthesized]
        while True:
            if any(
                search_state in current_origin_states_dict.values()
                for search_state in search_states
            ):
                earliest_state = [
                    search_state
                    for search_state in search_states
                    if search_state in current_origin_states_dict.values()
                ]
            search_states = [
                x["source"]  # type: ignore
                for x in colrev.record.RecordStateModel.transitions
                if x["dest"] in search_states
            ]
            if [] == search_states:
                break
        # print(f'earliest_state: {earliest_state}')

        # next: get the priority transition for the earliest states
        priority_transitions = [
            x["trigger"]
            for x in colrev.record.RecordStateModel.transitions
            if x["source"] in earliest_state
        ]

        priority_operations = list(set(priority_transitions))

        self.review_manager.logger.debug(f"priority_operations: {priority_operations}")
        return priority_operations

    def get_active_operations(self, *, current_origin_states_dict: dict) -> list:
        """Get the active processing functions"""

        active_operations: typing.List[str] = []
        for state in set(current_origin_states_dict.values()):
            valid_transitions = colrev.record.RecordStateModel.get_valid_transitions(
                state=state
            )
            active_operations.extend(valid_transitions)

        self.review_manager.logger.debug(f"active_operations: {set(active_operations)}")
        return active_operations

    def get_operation_in_progress(self, *, transitioned_records: list) -> list:
        """Get the operation currently in progress"""

        in_progress_operation = list(
            {x["operations_type"] for x in transitioned_records}
        )
        self.review_manager.logger.debug(
            f"in_progress_operation: {in_progress_operation}"
        )
        return in_progress_operation

    @dataclass
    class StatusStatsParent:
        """Parent class for StatusStatsCurrently and StatusStatsOverall"""

        # pylint: disable=too-many-instance-attributes
        # Note : StatusStatsCurrently and StatusStatsOverall start with the same frequencies
        def __init__(
            self,
            *,
            status_stats: StatusStats,
        ) -> None:
            self.status_stats = status_stats

            self.md_retrieved = self.__get_freq(colrev.record.RecordState.md_retrieved)

            self.md_imported = self.__get_freq(colrev.record.RecordState.md_imported)
            self.md_needs_manual_preparation = self.__get_freq(
                colrev.record.RecordState.md_needs_manual_preparation
            )
            self.md_prepared = self.__get_freq(colrev.record.RecordState.md_prepared)
            self.md_processed = self.__get_freq(colrev.record.RecordState.md_processed)
            self.rev_prescreen_excluded = self.__get_freq(
                colrev.record.RecordState.rev_prescreen_excluded
            )
            self.rev_prescreen_included = self.__get_freq(
                colrev.record.RecordState.rev_prescreen_included
            )
            self.pdf_needs_manual_retrieval = self.__get_freq(
                colrev.record.RecordState.pdf_needs_manual_retrieval
            )
            self.pdf_imported = self.__get_freq(colrev.record.RecordState.pdf_imported)
            self.pdf_not_available = self.__get_freq(
                colrev.record.RecordState.pdf_not_available
            )
            self.pdf_needs_manual_preparation = self.__get_freq(
                colrev.record.RecordState.pdf_needs_manual_preparation
            )
            self.pdf_prepared = self.__get_freq(colrev.record.RecordState.pdf_prepared)
            self.rev_excluded = self.__get_freq(colrev.record.RecordState.rev_excluded)
            self.rev_included = self.__get_freq(colrev.record.RecordState.rev_included)
            self.rev_synthesized = self.__get_freq(
                colrev.record.RecordState.rev_synthesized
            )
            self.md_duplicates_removed = self.status_stats.md_duplicates_removed

        def __get_freq(self, colrev_status: colrev.record.RecordState) -> int:
            return len([x for x in self.status_stats.status_list if colrev_status == x])

    @dataclass
    class StatusStatsCurrently(StatusStatsParent):
        """The current status statistics"""

        # pylint: disable=too-many-instance-attributes
        md_retrieved: int
        md_imported: int
        md_prepared: int
        md_needs_manual_preparation: int
        md_duplicates_removed: int
        md_processed: int
        non_processed: int
        rev_prescreen_excluded: int
        rev_prescreen_included: int
        pdf_needs_retrieval: int
        pdf_needs_manual_retrieval: int
        pdf_not_available: int
        pdf_imported: int
        pdf_needs_manual_preparation: int
        pdf_prepared: int
        rev_excluded: int
        rev_included: int
        rev_synthesized: int
        non_completed: int
        exclusion: dict

        def __init__(
            self,
            *,
            status_stats: StatusStats,
        ) -> None:
            self.exclusion: typing.Dict[str, int] = {}
            self.non_completed = 0
            self.non_processed = 0
            super().__init__(status_stats=status_stats)
            self.pdf_needs_retrieval = self.rev_prescreen_included

    @dataclass
    class StatusStatsOverall(StatusStatsParent):
        """The overall-status statistics (records currently/previously in each state)"""

        # pylint: disable=too-many-instance-attributes
        md_retrieved: int
        md_imported: int
        md_needs_manual_preparation: int
        md_prepared: int
        md_processed: int
        rev_prescreen: int
        rev_prescreen_excluded: int
        rev_prescreen_included: int
        pdf_needs_manual_retrieval: int
        pdf_imported: int
        pdf_not_available: int
        pdf_needs_manual_preparation: int
        pdf_prepared: int
        rev_excluded: int
        rev_included: int
        rev_screen: int
        rev_synthesized: int

        def __init__(
            self,
            *,
            status_stats: StatusStats,
        ) -> None:
            self.rev_screen = 0
            self.rev_prescreen = 0
            super().__init__(status_stats=status_stats)
            self.md_retrieved = self.__get_nr_search(
                search_dir=self.status_stats.review_manager.search_dir
            )

        def __get_nr_search(self, *, search_dir: Path) -> int:
            if not search_dir.is_dir():
                return 0
            bib_files = search_dir.glob("*.bib")
            number_search = 0
            for search_file in bib_files:
                # Note : skip md-prep sources
                if str(search_file.name).startswith("md_"):
                    continue
                number_search += self.status_stats.review_manager.dataset.get_nr_in_bib(
                    file_path=search_file
                )
            return number_search


if __name__ == "__main__":
    pass
