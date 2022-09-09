#!/usr/bin/env python3
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import auto
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import git
import zope.interface
from transitions import Machine

import colrev.exceptions as colrev_exceptions
import colrev.record

if TYPE_CHECKING:
    import colrev.review_manager


class ProcessType(Enum):
    # pylint: disable=invalid-name

    search = auto()
    load = auto()
    prep = auto()
    prep_man = auto()
    dedupe = auto()
    prescreen = auto()
    pdf_get = auto()
    pdf_get_man = auto()
    pdf_prep = auto()
    pdf_prep_man = auto()
    screen = auto()
    data = auto()

    format = auto()
    explore = auto()
    check = auto()

    def __str__(self):
        return f"{self.name}"


class Process:
    # pylint: disable=too-few-public-methods

    force_mode: bool

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        process_type: ProcessType,
        notify_state_transition_operation=True,
        debug=False,
    ) -> None:

        self.review_manager = review_manager
        self.force_mode = self.review_manager.force_mode

        self.type = process_type

        self.notify_state_transition_operation = notify_state_transition_operation
        if notify_state_transition_operation:
            self.review_manager.notify(process=self)
        else:
            self.review_manager.notify(process=self, state_transition=False)

        self.review_manager.debug_mode = debug

        self.cpus = 4

        # Note: the following call seems to block the flow (if debug is enabled)
        # self.review_manager.logger.debug(f"Created {self.type} process")

        # Note: we call review_manager.notify() in the subclasses
        # to make sure that the review_manager calls the right check_preconditions()

    def check_precondition(self) -> None:
        """Check the process precondition"""

        if (
            self.force_mode
            or "realtime" == self.review_manager.settings.project.review_type
        ):
            return

        def check_process_model_precondition() -> None:
            process_model = ProcessModel(
                process=self.type, review_manager=self.review_manager
            )
            process_model.check_process_precondition(process=self)

        def require_clean_repo_general(
            *, git_repo: git.Repo = None, ignore_pattern: list = None
        ) -> bool:

            if git_repo is None:
                git_repo = git.Repo(self.review_manager.path)

            # Note : not considering untracked files.

            if len(git_repo.index.diff("HEAD")) == 0:
                unstaged_changes = [item.a_path for item in git_repo.index.diff(None)]
                if (
                    self.review_manager.dataset.RECORDS_FILE_RELATIVE
                    in unstaged_changes
                ):
                    git_repo.index.add(
                        [self.review_manager.dataset.RECORDS_FILE_RELATIVE]
                    )

            # Principle: working tree always has to be clean
            # because processing functions may change content
            if git_repo.is_dirty(index=False):
                changed_files = [item.a_path for item in git_repo.index.diff(None)]
                raise colrev_exceptions.UnstagedGitChangesError(changed_files)

            if git_repo.is_dirty():
                if ignore_pattern is None:
                    changed_files = [
                        item.a_path for item in git_repo.index.diff(None)
                    ] + [
                        x.a_path
                        for x in git_repo.head.commit.diff()
                        if x.a_path not in [str(self.review_manager.STATUS_RELATIVE)]
                    ]
                    if len(changed_files) > 0:
                        raise colrev_exceptions.CleanRepoRequiredError(
                            changed_files, ""
                        )
                else:
                    changed_files = [
                        item.a_path
                        for item in git_repo.index.diff(None)
                        if not any(str(ip) in item.a_path for ip in ignore_pattern)
                    ] + [
                        x.a_path
                        for x in git_repo.head.commit.diff()
                        if not any(str(ip) in x.a_path for ip in ignore_pattern)
                    ]
                    if str(self.review_manager.STATUS_RELATIVE) in changed_files:
                        changed_files.remove(str(self.review_manager.STATUS_RELATIVE))
                    if changed_files:
                        raise colrev_exceptions.CleanRepoRequiredError(
                            changed_files, ",".join([str(x) for x in ignore_pattern])
                        )
            return True

        if ProcessType.load == self.type:
            require_clean_repo_general(
                ignore_pattern=[
                    self.review_manager.SEARCHDIR_RELATIVE,
                    self.review_manager.SETTINGS_RELATIVE,
                ]
            )
            check_process_model_precondition()

        elif ProcessType.prep == self.type:

            if self.notify_state_transition_operation:
                require_clean_repo_general()
                check_process_model_precondition()

        elif ProcessType.prep_man == self.type:
            require_clean_repo_general(
                ignore_pattern=[self.review_manager.dataset.RECORDS_FILE_RELATIVE]
            )
            check_process_model_precondition()

        elif ProcessType.dedupe == self.type:
            require_clean_repo_general()
            check_process_model_precondition()

        elif ProcessType.prescreen == self.type:
            require_clean_repo_general(
                ignore_pattern=[self.review_manager.dataset.RECORDS_FILE_RELATIVE]
            )
            check_process_model_precondition()

        elif ProcessType.pdf_get == self.type:
            require_clean_repo_general(
                ignore_pattern=[self.review_manager.PDF_DIRECTORY_RELATIVE]
            )
            check_process_model_precondition()

        elif ProcessType.pdf_get_man == self.type:
            require_clean_repo_general(
                ignore_pattern=[self.review_manager.PDF_DIRECTORY_RELATIVE]
            )
            check_process_model_precondition()

        elif ProcessType.pdf_prep == self.type:
            require_clean_repo_general()
            check_process_model_precondition()

        elif ProcessType.pdf_prep_man == self.type:
            # require_clean_repo_general(
            #     ignore_pattern=[self.review_manager.PDF_DIRECTORY_RELATIVE]
            # )
            # check_process_model_precondition()
            pass

        elif ProcessType.screen == self.type:
            require_clean_repo_general()
            check_process_model_precondition()

        elif ProcessType.data == self.type:
            # require_clean_repo_general(
            #     ignore_pattern=[
            #         # data.csv, paper.md etc.?,
            #     ]
            # )
            check_process_model_precondition()

        elif ProcessType.format == self.type:
            pass
        elif ProcessType.explore == self.type:
            pass
        elif ProcessType.check == self.type:
            pass


class FormatProcess(Process):
    # pylint: disable=too-few-public-methods

    def __init__(self, *, review_manager, notify: bool = True) -> None:
        super().__init__(review_manager=review_manager, process_type=ProcessType.format)
        if notify:
            self.review_manager.notify(process=self)


class CheckProcess(Process):
    # pylint: disable=too-few-public-methods

    def __init__(self, *, review_manager) -> None:
        super().__init__(
            review_manager=review_manager,
            process_type=ProcessType.check,
            notify_state_transition_operation=False,
        )


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
    for state in list(colrev.record.RecordState)
]


class ProcessModel:

    transitions = transitions = [
        {
            "trigger": "load",
            "source": colrev.record.RecordState.md_retrieved,
            "dest": colrev.record.RecordState.md_imported,
        },
        {
            "trigger": "prep",
            "source": colrev.record.RecordState.md_imported,
            "dest": colrev.record.RecordState.md_needs_manual_preparation,
        },
        {
            "trigger": "prep",
            "source": colrev.record.RecordState.md_imported,
            "dest": colrev.record.RecordState.md_prepared,
        },
        {
            "trigger": "prep_man",
            "source": colrev.record.RecordState.md_needs_manual_preparation,
            "dest": colrev.record.RecordState.md_prepared,
        },
        {
            "trigger": "dedupe",
            "source": colrev.record.RecordState.md_prepared,
            "dest": colrev.record.RecordState.md_processed,
        },
        {
            "trigger": "prescreen",
            "source": colrev.record.RecordState.md_processed,
            "dest": colrev.record.RecordState.rev_prescreen_excluded,
        },
        {
            "trigger": "prescreen",
            "source": colrev.record.RecordState.md_processed,
            "dest": colrev.record.RecordState.rev_prescreen_included,
        },
        {
            "trigger": "pdf_get",
            "source": colrev.record.RecordState.rev_prescreen_included,
            "dest": colrev.record.RecordState.pdf_imported,
        },
        {
            "trigger": "pdf_get",
            "source": colrev.record.RecordState.rev_prescreen_included,
            "dest": colrev.record.RecordState.pdf_needs_manual_retrieval,
        },
        {
            "trigger": "pdf_get_man",
            "source": colrev.record.RecordState.pdf_needs_manual_retrieval,
            "dest": colrev.record.RecordState.pdf_not_available,
        },
        {
            "trigger": "pdf_get_man",
            "source": colrev.record.RecordState.pdf_needs_manual_retrieval,
            "dest": colrev.record.RecordState.pdf_imported,
        },
        {
            "trigger": "pdf_prep",
            "source": colrev.record.RecordState.pdf_imported,
            "dest": colrev.record.RecordState.pdf_needs_manual_preparation,
        },
        {
            "trigger": "pdf_prep",
            "source": colrev.record.RecordState.pdf_imported,
            "dest": colrev.record.RecordState.pdf_prepared,
        },
        {
            "trigger": "pdf_prep_man",
            "source": colrev.record.RecordState.pdf_needs_manual_preparation,
            "dest": colrev.record.RecordState.pdf_prepared,
        },
        {
            "trigger": "screen",
            "source": colrev.record.RecordState.pdf_prepared,
            "dest": colrev.record.RecordState.rev_excluded,
        },
        {
            "trigger": "screen",
            "source": colrev.record.RecordState.pdf_prepared,
            "dest": colrev.record.RecordState.rev_included,
        },
        {
            "trigger": "data",
            "source": colrev.record.RecordState.rev_included,
            "dest": colrev.record.RecordState.rev_synthesized,
        },
    ]

    transitions_non_processing = [
        item for sublist in non_processing_transitions for item in sublist
    ]

    def __init__(
        self, *, state: str = None, process: ProcessType = None, review_manager=None
    ) -> None:

        if process is not None:
            start_states: list[str] = [
                str(x["source"])
                for x in self.transitions
                if str(process) == x["trigger"]
            ]
            self.state = start_states[0]
        elif state is not None:
            self.state = state
        else:
            print("ERROR: no process or state provided")

        if review_manager is not None:
            self.review_manager = review_manager

        logging.getLogger("transitions").setLevel(logging.WARNING)

        self.machine = Machine(
            model=self,
            states=colrev.record.RecordState,
            transitions=self.transitions + self.transitions_non_processing,
            initial=self.state,
        )

    def get_valid_transitions(self) -> list:
        return list(
            {x["trigger"] for x in self.transitions if x["source"] == self.state}
        )

    def get_preceding_states(self, *, state) -> set:
        preceding_states: set[colrev.record.RecordState] = set()
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

    def check_process_precondition(self, *, process: Process) -> None:

        if "True" == self.review_manager.settings.project.delay_automated_processing:
            cur_state_list = self.review_manager.dataset.get_states_set()
            self.review_manager.logger.debug(f"cur_state_list: {cur_state_list}")
            self.review_manager.logger.debug(f"precondition: {self.state}")
            required_absent = {
                str(x) for x in self.get_preceding_states(state=self.state)
            }
            self.review_manager.logger.debug(f"required_absent: {required_absent}")
            intersection = cur_state_list.intersection(required_absent)
            if (
                len(cur_state_list) == 0
                and not process.type.name == "load"  # type: ignore
            ):
                raise colrev_exceptions.NoRecordsError()
            if len(intersection) != 0:
                raise colrev_exceptions.ProcessOrderViolation(
                    process, self.state, intersection
                )


class SearchEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    source_identifier = zope.interface.Attribute("""Source identifier""")
    mode = zope.interface.Attribute("""Mode""")

    # pylint: disable=no-self-argument
    def run_search(search_operation, params: dict, feed_file: Path) -> None:
        pass

    def validate_params(query: str) -> None:
        pass


class SearchSourceEndpoint(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    source_identifier = zope.interface.Attribute("""Source identifier for provenance""")

    # pylint: disable=no-self-argument
    def heuristic(filename, data):
        pass

    def prepare(record):
        pass


class LoadEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    supported_extensions = zope.interface.Attribute("""List of supported extensions""")

    # pylint: disable=no-self-argument
    def load(load_operation, source):
        pass


class PrepEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    source_correction_hint = zope.interface.Attribute(
        """Hint on how to correct metadata at source"""
    )

    always_apply_changes = zope.interface.Attribute(
        """Flag indicating whether changes should always be applied
        (even if the colrev_status does not transition to md_prepared)"""
    )

    # pylint: disable=no-self-argument
    def prepare(prep_operation, prep_record):
        pass


class PrepManEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def prepare_manual(prep_man_operation, records):
        pass


class DedupeEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_dedupe(dedupe_operation):
        pass


class PrescreenEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_prescreen(prescreen_operation, records: dict, split: list) -> dict:
        pass


class PDFGetEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def get_pdf(pdf_get_operation, record):
        return record


class PDFGetManEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def get_man_pdf(pdf_get_man_operation, records):
        return records


class PDFPrepEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=unused-argument
    # pylint: disable=no-self-argument
    def prep_pdf(pdf_prep_operation, record, pad) -> dict:
        return record.data


class PDFPrepManEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def prep_man_pdf(pdf_prep_man_operation, records):
        return records


class ScreenEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_screen(screen_operation, records: dict, split: list) -> dict:
        pass


class DataEndpoint(zope.interface.Interface):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    # pylint: disable=no-method-argument
    def get_default_setup() -> dict:  # type: ignore
        return {}

    def update_data(
        data_operation, records: dict, synthesized_record_status_matrix: dict
    ) -> None:
        pass

    def update_record_status_matrix(
        data_operation, synthesized_record_status_matrix, endpoint_identifier
    ) -> None:
        pass


@dataclass
class DefaultSettings:
    name: str


if __name__ == "__main__":
    pass
