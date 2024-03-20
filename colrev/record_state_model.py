#! /usr/bin/env python
"""The RecordStateModel."""
from __future__ import annotations

import logging

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.qm.colrev_id
import colrev.qm.colrev_pdf_id
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.constants import Operations
from colrev.constants import RecordState

non_processing_transitions = [
    [
        {
            "trigger": "format",
            "source": state,
            "dest": state,
        },
        {
            "trigger": "explore",
            "source": state,
            "dest": state,
        },
        {
            "trigger": "check",
            "source": state,
            "dest": state,
        },
    ]
    for state in list(RecordState)
]


class RecordStateModel:
    """The RecordStateModel describes transitions between RecordStates"""

    transitions = [
        {
            "trigger": Operations.LOAD,
            "source": RecordState.md_retrieved,
            "dest": RecordState.md_imported,
        },
        {
            "trigger": Operations.PREP,
            "source": RecordState.md_imported,
            "dest": RecordState.md_needs_manual_preparation,
        },
        {
            "trigger": Operations.PREP,
            "source": RecordState.md_imported,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": Operations.PREP_MAN,
            "source": RecordState.md_needs_manual_preparation,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": Operations.DEDUPE,
            "source": RecordState.md_prepared,
            "dest": RecordState.md_processed,
        },
        {
            "trigger": Operations.PRESCREEN,
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_excluded,
        },
        {
            "trigger": Operations.PRESCREEN,
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_included,
        },
        {
            "trigger": Operations.PDF_GET,
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": Operations.PDF_GET,
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_needs_manual_retrieval,
        },
        {
            "trigger": Operations.PDF_GET_MAN,
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_not_available,
        },
        {
            "trigger": Operations.PDF_GET_MAN,
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": Operations.PDF_PREP,
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_needs_manual_preparation,
        },
        {
            "trigger": Operations.PDF_PREP,
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": Operations.PDF_PREP_MAN,
            "source": RecordState.pdf_needs_manual_preparation,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": Operations.SCREEN,
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_excluded,
        },
        {
            "trigger": Operations.SCREEN,
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_included,
        },
        {
            "trigger": Operations.DATA,
            "source": RecordState.rev_included,
            "dest": RecordState.rev_synthesized,
        },
    ]

    transitions_non_processing = [
        item for sublist in non_processing_transitions for item in sublist
    ]

    # from transitions import Machine
    # def __init__(
    #     self,
    #     *,
    #     state: RecordState,
    # ) -> None:
    #     self.state = state

    #     self.machine = Machine(
    #         model=self,
    #         states=RecordState,
    #         transitions=self.transitions + self.transitions_non_processing,
    #         initial=self.state,
    #     )

    @classmethod
    def get_valid_transitions(cls, *, state: RecordState) -> set:
        """Get the list of valid transitions"""
        logging.getLogger("transitions").setLevel(logging.WARNING)
        return set({x["trigger"] for x in cls.transitions if x["source"] == state})

    @classmethod
    def get_preceding_states(cls, *, state: RecordState) -> set:
        """Get the states preceding the state that is given as a parameter"""

        logging.getLogger("transitions").setLevel(logging.WARNING)
        preceding_states: set[RecordState] = set()
        added = True
        while added:
            preceding_states_size = len(preceding_states)
            for transition in RecordStateModel.transitions:
                if (
                    transition["dest"] in preceding_states
                    or state == transition["dest"]
                ):
                    preceding_states.add(transition["source"])  # type: ignore
            if preceding_states_size == len(preceding_states):
                added = False
        return preceding_states

    @classmethod
    def check_operation_precondition(
        cls, operation: colrev.operation.Operation
    ) -> None:
        """Check the preconditions for an operation"""

        def get_states_set() -> set:
            if not operation.review_manager.get_path(Filepaths.RECORDS_FILE).is_file():
                return set()
            records_headers = operation.review_manager.dataset.load_records_dict(
                header_only=True
            )
            record_header_list = list(records_headers.values())

            return {el[Fields.STATUS] for el in record_header_list}

        if operation.review_manager.settings.project.delay_automated_processing:
            start_states: list[str] = [
                str(x["source"])
                for x in RecordStateModel.transitions
                if str(operation.type) == x["trigger"]
            ]
            state = RecordState[start_states[0]]

            cur_state_list = get_states_set()
            # self.review_manager.logger.debug(f"cur_state_list: {cur_state_list}")
            # self.review_manager.logger.debug(f"precondition: {self.state}")
            required_absent = cls.get_preceding_states(state=state)
            # self.review_manager.logger.debug(f"required_absent: {required_absent}")
            violating_states = cur_state_list.intersection(required_absent)
            if (
                len(cur_state_list) == 0
                and not operation.type.name == "load"  # type: ignore
            ):
                raise colrev_exceptions.NoRecordsError()
            if len(violating_states) != 0:
                raise colrev_exceptions.ProcessOrderViolation(
                    operation.type.name, str(state), list(violating_states)
                )
