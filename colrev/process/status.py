#! /usr/bin/env python3
"""CoLRev status stats."""
from __future__ import annotations

import typing

from pydantic import BaseModel

import colrev.loader.load_utils
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.process.model import ProcessModel

if typing.TYPE_CHECKING:
    import colrev.review_manager
    import colrev.record.record


class StatusStatsCurrently(BaseModel):
    """The current status statistics"""

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
    pdf_needs_retrieval: int
    non_completed: int
    exclusion: dict
    md_needs_manual_preparation: int
    pdf_needs_manual_retrieval: int
    pdf_needs_manual_preparation: int


class StatusStatsOverall(BaseModel):
    """The overall-status statistics (records currently/previously in each state)"""

    # pylint: disable=too-many-instance-attributes
    md_retrieved: int
    md_imported: int
    md_prepared: int
    md_processed: int
    rev_prescreen_excluded: int
    rev_prescreen_included: int
    rev_prescreen: int
    pdf_not_available: int
    pdf_imported: int
    pdf_prepared: int
    rev_screen: int
    rev_excluded: int
    rev_included: int
    rev_synthesized: int


def _get_origin_states_dict(records: dict) -> dict:
    current_origin_states_dict = {}
    for record_dict in records.values():
        for origin in record_dict[Fields.ORIGIN]:
            current_origin_states_dict[origin] = record_dict[Fields.STATUS]
    return current_origin_states_dict


def _get_screening_statistics(
    *,
    review_manager: colrev.review_manager.ReviewManager,
    records: dict,
) -> dict:
    screening_criteria = [
        x[Fields.SCREENING_CRITERIA]
        for x in records.values()
        if x.get(Fields.SCREENING_CRITERIA, "") not in ["", "NA"]
    ]
    criteria = list(review_manager.settings.screen.criteria.keys())
    screening_statistics = {crit: 0 for crit in criteria}
    for screening_case in screening_criteria:
        for criterion in screening_case.split(";"):
            criterion_name, decision = criterion.split("=")
            if decision == "out":
                screening_statistics[criterion_name] += 1
    return screening_statistics


def _get_duplicates_removed(records: dict) -> int:
    md_duplicates_removed = 0
    for record_dict in records.values():
        md_duplicates_removed += (
            len([o for o in record_dict[Fields.ORIGIN] if not o.startswith("md_")]) - 1
        )
    return md_duplicates_removed


def _get_nr_origins(records: dict) -> int:
    origin_list = [x[Fields.ORIGIN] for x in records.values()]
    nr_origins = 0
    for origin in origin_list:
        nr_origins += len([o for o in origin if not o.startswith("md_")])
    return nr_origins


def _get_nr_incomplete(origin_states_dict: dict) -> int:
    """Get the number of incomplete records"""
    return len(
        [
            x
            for x in list(origin_states_dict.values())
            if x
            not in [
                RecordState.rev_synthesized,
                RecordState.rev_excluded,
                RecordState.rev_prescreen_excluded,
                RecordState.pdf_not_available,
            ]
        ]
    )


def _get_freq(*, status_list: list, colrev_status: RecordState) -> int:
    return len([x for x in status_list if colrev_status == x])


def _get_status_stats_currently(
    status_list: list, records: dict, screening_statistics: dict, md_retrieved: int
) -> StatusStatsCurrently:
    precreen_included = _get_freq(
        status_list=status_list, colrev_status=RecordState.rev_prescreen_included
    )
    data = {
        "md_retrieved": md_retrieved,
        "md_imported": _get_freq(
            status_list=status_list, colrev_status=RecordState.md_imported
        ),
        "md_prepared": _get_freq(
            status_list=status_list, colrev_status=RecordState.md_prepared
        ),
        "md_processed": _get_freq(
            status_list=status_list, colrev_status=RecordState.md_processed
        ),
        "rev_prescreen_excluded": _get_freq(
            status_list=status_list, colrev_status=RecordState.rev_prescreen_excluded
        ),
        "rev_prescreen_included": precreen_included,
        "pdf_imported": _get_freq(
            status_list=status_list, colrev_status=RecordState.pdf_imported
        ),
        "pdf_not_available": _get_freq(
            status_list=status_list, colrev_status=RecordState.pdf_not_available
        ),
        "pdf_prepared": _get_freq(
            status_list=status_list, colrev_status=RecordState.pdf_prepared
        ),
        "rev_excluded": _get_freq(
            status_list=status_list, colrev_status=RecordState.rev_excluded
        ),
        "rev_included": _get_freq(
            status_list=status_list, colrev_status=RecordState.rev_included
        ),
        "rev_synthesized": _get_freq(
            status_list=status_list, colrev_status=RecordState.rev_synthesized
        ),
        "pdf_needs_retrieval": precreen_included,
        "exclusion": screening_statistics,
        "md_needs_manual_preparation": _get_freq(
            status_list=status_list,
            colrev_status=RecordState.md_needs_manual_preparation,
        ),
        "pdf_needs_manual_retrieval": _get_freq(
            status_list=status_list,
            colrev_status=RecordState.pdf_needs_manual_retrieval,
        ),
        "pdf_needs_manual_preparation": _get_freq(
            status_list=status_list,
            colrev_status=RecordState.pdf_needs_manual_preparation,
        ),
        "non_completed": len(
            [
                r
                for r in records.values()
                if r[Fields.STATUS]
                not in [
                    RecordState.rev_synthesized,
                    RecordState.rev_prescreen_excluded,
                    RecordState.pdf_not_available,
                    RecordState.rev_excluded,
                ]
            ]
        ),
    }

    return StatusStatsCurrently(**data)


def _get_cumulative_freq(*, status_list: list, colrev_status: RecordState) -> int:
    return len(
        [
            x
            for x in status_list
            if x in RecordState.get_post_x_states(state=colrev_status)
        ]
    )


def _get_md_retrieved(sources: list) -> int:
    md_retrieved = 0
    for source in sources:
        if not source.is_md_source():
            nr_in_file = colrev.loader.load_utils.get_nr_records(source.filename)
            md_retrieved += nr_in_file
    return md_retrieved


def _get_currently_md_retrieved(origin_states_dict: dict, md_retrieved: int) -> int:

    # select records that are not md_ records
    # (origin_states_dict only has records beyond md_retrieved)
    non_md_records = {
        k: v for k, v in origin_states_dict.items() if not k.startswith("md_")
    }

    return md_retrieved - len(non_md_records)


def _get_status_stats_overall(
    status_list: list, records: dict, md_retrieved: int
) -> StatusStatsOverall:

    data = {
        "md_retrieved": md_retrieved,
        "md_imported": len(records.values()),
        "md_prepared": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.md_prepared
        ),
        "md_processed": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.md_processed
        ),
        "rev_prescreen": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.md_processed
        ),
        "rev_prescreen_included": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.rev_prescreen_included
        ),
        "pdf_imported": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.pdf_imported
        ),
        "pdf_prepared": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.pdf_prepared
        ),
        "rev_screen": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.pdf_prepared
        ),
        "rev_included": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.rev_included
        ),
        "rev_synthesized": _get_cumulative_freq(
            status_list=status_list, colrev_status=RecordState.rev_synthesized
        ),
        # Note: temporary states (_man_*) should not be covered in StatusStatsOverall
        "rev_prescreen_excluded": _get_freq(
            status_list=status_list, colrev_status=RecordState.rev_prescreen_excluded
        ),
        "rev_excluded": _get_freq(
            status_list=status_list, colrev_status=RecordState.rev_excluded
        ),
        "pdf_not_available": _get_freq(
            status_list=status_list, colrev_status=RecordState.pdf_not_available
        ),
    }

    return StatusStatsOverall(**data)


def _get_nr_curated_records(
    records: dict, curated: int, overall: StatusStatsOverall
) -> int:
    nr_curated_records = len(
        [
            r
            for r in records.values()
            if colrev.record.record.Record(r).masterdata_is_curated()
        ]
    )
    if curated:  # pragma: no cover
        nr_curated_records = overall.md_processed
    return nr_curated_records


def _get_perc_curated(
    overall: StatusStatsOverall,
    currently: StatusStatsCurrently,
    nr_curated_records: int,
) -> float:
    perc_curated = 0.0
    denominator = (
        overall.md_processed
        + currently.md_prepared
        + currently.md_needs_manual_preparation
        + currently.md_imported
    )
    if denominator > 0:
        perc_curated = int((nr_curated_records / (denominator)) * 100)
    return perc_curated


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


def _get_completed_atomic_steps(
    records: dict, currently: StatusStatsCurrently, md_duplicates_removed: int
) -> int:
    """Get the number of completed atomic steps"""
    completed_steps = 0
    for record_dict in records.values():
        completed_steps += REQUIRED_ATOMIC_STEPS[record_dict[Fields.STATUS]]
    completed_steps += 4 * md_duplicates_removed
    completed_steps += currently.md_retrieved  # not in records
    return completed_steps


def _get_atomic_steps(
    overall: StatusStatsOverall,
    currently: StatusStatsCurrently,
    md_duplicates_removed: int,
) -> int:
    return (
        # initially, all records have to pass 9 operations (including search)
        9 * overall.md_retrieved
        # for removed duplicates, 5 operations are no longer needed
        - 5 * md_duplicates_removed
        # for rev_prescreen_excluded, 4 operations are no longer needed
        - 4 * currently.rev_prescreen_excluded
        - 3 * currently.pdf_not_available
        - currently.rev_excluded
    )


# pylint: disable=no-member
def get_status_stats(
    *,
    review_manager: colrev.review_manager.ReviewManager,
    records: dict,
) -> StatusStats:
    """Get the status statistics"""

    origin_states_dict = _get_origin_states_dict(records)

    screening_statistics = _get_screening_statistics(
        review_manager=review_manager, records=records
    )
    status_list = [x[Fields.STATUS] for x in records.values()]
    sources = review_manager.settings.sources
    md_retrieved = _get_md_retrieved(sources)
    currently = _get_status_stats_currently(
        status_list, records, screening_statistics, md_retrieved
    )
    overall = _get_status_stats_overall(status_list, records, md_retrieved)
    currently.md_retrieved = _get_currently_md_retrieved(
        origin_states_dict, md_retrieved
    )
    nr_curated_records = _get_nr_curated_records(
        records, review_manager.settings.is_curated_masterdata_repo(), overall
    )
    md_duplicates_removed = _get_duplicates_removed(records)
    nr_incomplete = _get_nr_incomplete(origin_states_dict)

    data = {
        "screening_statistics": screening_statistics,
        "md_duplicates_removed": md_duplicates_removed,
        "nr_origins": _get_nr_origins(records),
        "nr_incomplete": nr_incomplete,
        "overall": overall,
        "currently": currently,
        "nr_curated_records": nr_curated_records,
        "perc_curated": _get_perc_curated(overall, currently, nr_curated_records),
        "completed_atomic_steps": _get_completed_atomic_steps(
            records, currently, md_duplicates_removed
        ),
        "atomic_steps": _get_atomic_steps(overall, currently, md_duplicates_removed),
        "completeness_condition": (nr_incomplete == 0)
        and (currently.md_retrieved == 0),
        "origin_states_dict": origin_states_dict,
    }

    return StatusStats(**data)


class StatusStats(BaseModel):
    """Data class for status statistics"""

    # pylint: disable=too-many-instance-attributes
    atomic_steps: int
    nr_curated_records: int
    perc_curated: float
    md_duplicates_removed: int
    currently: StatusStatsCurrently
    overall: StatusStatsOverall
    completed_atomic_steps: int
    completeness_condition: bool
    nr_incomplete: int
    nr_origins: int
    screening_statistics: dict

    origin_states_dict: dict

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

    def get_transitioned_records(
        self, review_manager: colrev.review_manager.ReviewManager
    ) -> list[typing.Dict]:
        """Get the transitioned records"""

        committed_origin_states_dict = (
            review_manager.dataset.get_committed_origin_state_dict()
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
                if (
                    x["source"] == transitioned_record["source"]
                    and x["dest"] == transitioned_record["dest"]
                )
                # Allow for reverse transitions
                or (
                    x["source"] == transitioned_record["dest"]
                    and x["dest"] == transitioned_record["source"]
                )
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

        return {str(x["type"]) for x in transitioned_records}
