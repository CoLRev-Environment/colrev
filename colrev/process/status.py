#! /usr/bin/env python3
"""CoLRev status stats."""
from __future__ import annotations

import typing
from dataclasses import dataclass

import colrev.process.operation
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.process.model import ProcessModel


@dataclass
class StatusStats:
    """Data class for status statistics"""

    # pylint: disable=too-many-instance-attributes
    atomic_steps: int
    nr_curated_records: int
    md_duplicates_removed: int
    currently: StatusStatsCurrently
    overall: StatusStatsOverall
    completed_atomic_steps: int
    completeness_condition: bool

    REQUIRED_ATOMIC_STEPS = {
        RecordState.md_retrieved: 1,
        RecordState.md_imported: 2,
        # note: md_needs_manual_preparation: prep-operation not yet completed successfully.
        RecordState.md_needs_manual_preparation: 2,
        RecordState.md_prepared: 3,
        RecordState.md_processed: 4,
        RecordState.rev_prescreen_included: 5,
        RecordState.rev_prescreen_excluded: 5,
        RecordState.pdf_needs_manual_retrieval: 5,
        RecordState.pdf_imported: 6,
        RecordState.pdf_needs_manual_preparation: 6,
        RecordState.pdf_not_available: 7,
        RecordState.pdf_prepared: 7,
        RecordState.rev_excluded: 8,
        RecordState.rev_included: 8,
        RecordState.rev_synthesized: 9,
    }

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        records: dict,
    ) -> None:
        self.review_manager = review_manager
        self.records = records
        self.origin_states_dict = self._get_origin_states_dict()

        self.status_list = [x[Fields.STATUS] for x in self.records.values()]
        self.screening_statistics = self._get_screening_statistics()
        self.md_duplicates_removed = self._get_duplicates_removed()
        self.nr_origins = self._get_nr_origins()
        self.nr_incomplete = self._get_nr_incomplete()

        self.overall = StatusStatsOverall(status_stats=self)
        self.currently = StatusStatsCurrently(status_stats=self)

        self.nr_curated_records = self._get_nr_curated_records()
        self.perc_curated = self._get_perc_curated()

        self.completed_atomic_steps = self._get_completed_atomic_steps()
        self.atomic_steps = self._get_atomic_steps()

        self.completeness_condition = (self.nr_incomplete == 0) and (
            self.currently.md_retrieved == 0
        )

    def _get_atomic_steps(self) -> int:
        return (
            # initially, all records have to pass 9 operations (including search)
            9 * self.overall.md_retrieved
            # for removed duplicates, 5 operations are no longer needed
            - 5 * self.md_duplicates_removed
            # for rev_prescreen_excluded, 4 operations are no longer needed
            - 4 * self.currently.rev_prescreen_excluded
            - 3 * self.currently.pdf_not_available
            - self.currently.rev_excluded
        )

    def _get_origin_states_dict(self) -> dict:
        current_origin_states_dict = {}
        for record_dict in self.records.values():
            for origin in record_dict[Fields.ORIGIN]:
                current_origin_states_dict[origin] = record_dict[Fields.STATUS]
        return current_origin_states_dict

    def _get_perc_curated(self) -> float:
        perc_curated = 0.0
        denominator = (
            self.overall.md_processed
            + self.currently.md_prepared
            + self.currently.md_needs_manual_preparation
            + self.currently.md_imported
        )
        if denominator > 0:
            perc_curated = int((self.nr_curated_records / (denominator)) * 100)
        return perc_curated

    def _get_nr_curated_records(self) -> int:
        nr_curated_records = len(
            [
                r
                for r in self.records.values()
                if colrev.record.record.Record(r).masterdata_is_curated()
            ]
        )
        if (
            self.review_manager.settings.is_curated_masterdata_repo()
        ):  # pragma: no cover
            nr_curated_records = self.overall.md_processed
        return nr_curated_records

    def _get_nr_origins(self) -> int:
        origin_list = [x[Fields.ORIGIN] for x in self.records.values()]
        nr_origins = 0
        for origin in origin_list:
            nr_origins += len([o for o in origin if not o.startswith("md_")])
        return nr_origins

    def _get_duplicates_removed(self) -> int:
        md_duplicates_removed = 0
        for record_dict in self.records.values():
            md_duplicates_removed += (
                len([o for o in record_dict[Fields.ORIGIN] if not o.startswith("md_")])
                - 1
            )
        return md_duplicates_removed

    def _get_nr_incomplete(self) -> int:
        """Get the number of incomplete records"""
        return len(
            [
                x
                for x in list(self.origin_states_dict.values())
                if x
                not in [
                    RecordState.rev_synthesized,
                    RecordState.rev_excluded,
                    RecordState.rev_prescreen_excluded,
                    RecordState.pdf_not_available,
                ]
            ]
        )

    def _get_screening_statistics(self) -> dict:
        screening_criteria = [
            x[Fields.SCREENING_CRITERIA]
            for x in self.records.values()
            if x.get(Fields.SCREENING_CRITERIA, "") not in ["", "NA"]
        ]
        criteria = list(self.review_manager.settings.screen.criteria.keys())
        screening_statistics = {crit: 0 for crit in criteria}
        for screening_case in screening_criteria:
            for criterion in screening_case.split(";"):
                criterion_name, decision = criterion.split("=")
                if decision == "out":
                    screening_statistics[criterion_name] += 1
        return screening_statistics

    def _get_completed_atomic_steps(self) -> int:
        """Get the number of completed atomic steps"""
        completed_steps = 0
        for record_dict in self.records.values():
            completed_steps += self.REQUIRED_ATOMIC_STEPS[record_dict[Fields.STATUS]]
        completed_steps += 4 * self.md_duplicates_removed
        completed_steps += self.currently.md_retrieved  # not in records
        return completed_steps

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
        if self.currently.pdf_imported > 0:  # pragma: no cover
            infos.append(f"{self.currently.pdf_imported} to prepare")
        if self.currently.pdf_needs_manual_preparation > 0:  # pragma: no cover
            infos.append(
                f"{self.currently.pdf_needs_manual_preparation} to prepare manually"
            )
        return ", ".join(infos)

    def get_transitioned_records(self) -> list[typing.Dict]:
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
                "dest": self.origin_states_dict.get(
                    committed_origin, "no_source_state"
                ),
            }

            if transitioned_record["source"] == transitioned_record["dest"]:
                continue  # no_transition

            operations_type = [
                x["trigger"]
                for x in ProcessModel.transitions
                if x["source"] == transitioned_record["source"]
                and x["dest"] == transitioned_record["dest"]
            ]
            if len(operations_type) == 0:
                transitioned_record["type"] = "invalid_transition"
            else:
                transitioned_record["type"] = operations_type[0]

            transitioned_records.append(transitioned_record)

        return transitioned_records

    def get_priority_operations(self) -> list:
        """Get the priority operations"""

        # get "earliest" states (going backward)
        earliest_state = []
        search_states = [RecordState.rev_synthesized]
        while True:
            if any(
                search_state in self.origin_states_dict.values()
                for search_state in search_states
            ):
                earliest_state = [
                    search_state
                    for search_state in search_states
                    if search_state in self.origin_states_dict.values()
                ]
            search_states = [
                x["source"]  # type: ignore
                for x in ProcessModel.transitions
                if x["dest"] in search_states
            ]
            if [] == search_states:
                break

        # next: get the priority transition for the earliest states
        priority_transitions = [
            x["trigger"]
            for x in ProcessModel.transitions
            if x["source"] in earliest_state
        ]

        return list(set(priority_transitions))

    def get_active_operations(self) -> list:
        """Get the active processing functions"""

        active_operations: typing.List[str] = []
        for state in set(self.origin_states_dict.values()):
            valid_transitions = ProcessModel.get_valid_transitions(state=state)
            active_operations.extend(valid_transitions)

        return active_operations

    def get_operation_in_progress(self, *, transitioned_records: list) -> set:
        """Get the operation currently in progress"""

        return {x["type"] for x in transitioned_records}


@dataclass
class StatusStatsParent:
    """Parent class for StatusStatsCurrently and StatusStatsOverall"""

    # pylint: disable=too-many-instance-attributes
    md_retrieved: int
    md_imported: int
    md_prepared: int
    md_processed: int
    rev_prescreen_excluded: int
    rev_prescreen_included: int
    pdf_not_available: int
    pdf_imported: int
    pdf_prepared: int
    rev_excluded: int
    rev_included: int
    rev_synthesized: int

    # Note : StatusStatsCurrently and StatusStatsOverall start with the same frequencies
    def __init__(
        self,
        *,
        status_stats: StatusStats,
    ) -> None:
        self.status_stats = status_stats

    def _get_freq(self, colrev_status: RecordState) -> int:
        return len([x for x in self.status_stats.status_list if colrev_status == x])


@dataclass
class StatusStatsCurrently(StatusStatsParent):
    """The current status statistics"""

    # pylint: disable=too-many-instance-attributes

    pdf_needs_retrieval: int
    non_completed: (
        int  # for sharing (all records must bet excluded/pdf_not_available/synthesized)
    )
    exclusion: dict
    md_needs_manual_preparation: int
    pdf_needs_manual_retrieval: int
    pdf_needs_manual_preparation: int

    def __init__(
        self,
        *,
        status_stats: StatusStats,
    ) -> None:

        super().__init__(status_stats=status_stats)
        self.md_retrieved = max(
            status_stats.overall.md_retrieved
            - status_stats.overall.md_imported
            - status_stats.nr_origins,
            0,
        )

        self.md_imported = self._get_freq(RecordState.md_imported)
        self.md_prepared = self._get_freq(RecordState.md_prepared)
        self.md_processed = self._get_freq(RecordState.md_processed)
        self.rev_prescreen_excluded = self._get_freq(RecordState.rev_prescreen_excluded)
        self.rev_prescreen_included = self._get_freq(RecordState.rev_prescreen_included)
        self.pdf_imported = self._get_freq(RecordState.pdf_imported)
        self.pdf_not_available = self._get_freq(RecordState.pdf_not_available)
        self.pdf_prepared = self._get_freq(RecordState.pdf_prepared)
        self.rev_excluded = self._get_freq(RecordState.rev_excluded)
        self.rev_included = self._get_freq(RecordState.rev_included)
        self.rev_synthesized = self._get_freq(RecordState.rev_synthesized)

        self.pdf_needs_retrieval = self.rev_prescreen_included
        self.exclusion = status_stats.screening_statistics
        self.pdf_needs_retrieval = self.rev_prescreen_included

        self.md_needs_manual_preparation = self._get_freq(
            RecordState.md_needs_manual_preparation
        )
        self.pdf_needs_manual_retrieval = self._get_freq(
            RecordState.pdf_needs_manual_retrieval
        )
        self.pdf_needs_manual_preparation = self._get_freq(
            RecordState.pdf_needs_manual_preparation
        )
        self.non_completed = len(
            [
                r
                for r in status_stats.records.values()
                if r[Fields.STATUS]
                not in [
                    RecordState.rev_synthesized,
                    RecordState.rev_prescreen_excluded,
                    RecordState.pdf_not_available,
                    RecordState.rev_excluded,
                ]
            ]
        )


@dataclass
class StatusStatsOverall(StatusStatsParent):
    """The overall-status statistics (records currently/previously in each state)"""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        *,
        status_stats: StatusStats,
    ) -> None:

        super().__init__(status_stats=status_stats)

        self.md_retrieved = self._get_md_retrieved(status_stats)
        self.md_imported = len(status_stats.records.values())
        self.md_prepared = self._get_cumulative_freq(RecordState.md_prepared)
        self.md_processed = self._get_cumulative_freq(RecordState.md_processed)
        self.rev_prescreen = self._get_cumulative_freq(RecordState.md_processed)
        self.rev_prescreen_included = self._get_cumulative_freq(
            RecordState.rev_prescreen_included
        )
        self.pdf_imported = self._get_cumulative_freq(RecordState.pdf_imported)
        self.pdf_prepared = self._get_cumulative_freq(RecordState.pdf_prepared)
        self.rev_screen = self._get_cumulative_freq(RecordState.pdf_prepared)
        self.rev_included = self._get_cumulative_freq(RecordState.rev_included)
        self.rev_synthesized = self._get_cumulative_freq(RecordState.rev_synthesized)

        # Note: temporary states (_man_*) should not be covered in StatusStatsOverall
        self.rev_prescreen_excluded = self._get_freq(RecordState.rev_prescreen_excluded)
        self.rev_excluded = self._get_freq(RecordState.rev_excluded)
        self.pdf_not_available = self._get_freq(RecordState.pdf_not_available)

    def _get_cumulative_freq(self, colrev_status: RecordState) -> int:
        return len(
            [
                x
                for x in self.status_stats.status_list
                if x in RecordState.get_post_x_states(state=colrev_status)
            ]
        )

    def _get_md_retrieved(self, status_stats: StatusStats) -> int:
        md_retrieved = 0
        for source in status_stats.review_manager.settings.sources:
            if not source.is_md_source():
                nr_in_file = colrev.loader.load_utils.get_nr_records(source.filename)
                md_retrieved += nr_in_file
        return md_retrieved
