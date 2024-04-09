#! /usr/bin/env python
"""The process model."""
from __future__ import annotations

import logging
import typing

import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.process.operation


class ProcessModel:
    """The ProcessModel describes transitions between RecordStates"""

    transitions = [
        {
            "trigger": OperationsType.load,
            "source": RecordState.md_retrieved,
            "dest": RecordState.md_imported,
        },
        {
            "trigger": OperationsType.prep,
            "source": RecordState.md_imported,
            "dest": RecordState.md_needs_manual_preparation,
        },
        {
            "trigger": OperationsType.prep,
            "source": RecordState.md_imported,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": OperationsType.prep_man,
            "source": RecordState.md_needs_manual_preparation,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": OperationsType.dedupe,
            "source": RecordState.md_prepared,
            "dest": RecordState.md_processed,
        },
        {
            "trigger": OperationsType.prescreen,
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_excluded,
        },
        {
            "trigger": OperationsType.prescreen,
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_included,
        },
        {
            "trigger": OperationsType.pdf_get,
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": OperationsType.pdf_get,
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_needs_manual_retrieval,
        },
        {
            "trigger": OperationsType.pdf_get_man,
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_not_available,
        },
        {
            "trigger": OperationsType.pdf_get_man,
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": OperationsType.pdf_prep,
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_needs_manual_preparation,
        },
        {
            "trigger": OperationsType.pdf_prep,
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": OperationsType.pdf_prep_man,
            "source": RecordState.pdf_needs_manual_preparation,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": OperationsType.screen,
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_excluded,
        },
        {
            "trigger": OperationsType.screen,
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_included,
        },
        {
            "trigger": OperationsType.data,
            "source": RecordState.rev_included,
            "dest": RecordState.rev_synthesized,
        },
    ]

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
            for transition in ProcessModel.transitions:
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
        cls, operation: colrev.process.operation.Operation
    ) -> None:
        """Check the preconditions for an operation"""

        def get_states_set() -> set:
            records_headers = operation.review_manager.dataset.load_records_dict(
                header_only=True
            )
            record_header_list = list(records_headers.values())

            return {el[Fields.STATUS] for el in record_header_list}

        if operation.review_manager.settings.project.delay_automated_processing:
            start_states = [
                x["source"]
                for x in ProcessModel.transitions
                if operation.type == x["trigger"]
            ]
            state: RecordState = start_states[0]  # type: ignore

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
