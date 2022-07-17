#!/usr/bin/env python3
import typing
from dataclasses import dataclass
from enum import auto
from enum import Enum
from pathlib import Path

import git
import zope.interface
from transitions import Machine

from colrev_core.exceptions import CleanRepoRequiredError
from colrev_core.exceptions import NoRecordsError
from colrev_core.exceptions import ProcessOrderViolation
from colrev_core.exceptions import UnstagedGitChangesError
from colrev_core.record import RecordState


class ProcessType(Enum):
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
    def __init__(
        self,
        *,
        REVIEW_MANAGER,
        type: ProcessType,
        notify_state_transition_process=True,
        debug=False,
    ):

        self.REVIEW_MANAGER = REVIEW_MANAGER
        self.force_mode = self.REVIEW_MANAGER.force_mode

        self.type = type

        self.notify_state_transition_process = notify_state_transition_process
        if notify_state_transition_process:
            self.REVIEW_MANAGER.notify(process=self)
        else:
            self.REVIEW_MANAGER.notify(process=self, state_transition=False)

        if debug:
            self.REVIEW_MANAGER.DEBUG_MODE = True
        else:
            self.REVIEW_MANAGER.DEBUG_MODE = False
        self.CPUS = 4

        # Note: the following call seems to block the flow (if debug is enabled)
        # self.REVIEW_MANAGER.logger.debug(f"Created {self.type} process")

        # Note: we call REVIEW_MANAGER.notify() in the subclasses
        # to make sure that the REVIEW_MANAGER calls the right check_preconditions()

    def check_precondition(self) -> None:
        """Check the process precondition"""

        if (
            self.force_mode
            or "realtime" == self.REVIEW_MANAGER.settings.project.review_type
        ):
            return

        def check_process_model_precondition() -> None:
            PROCESS_MODEL = ProcessModel(
                process=self.type, REVIEW_MANAGER=self.REVIEW_MANAGER
            )
            PROCESS_MODEL.check_process_precondition(process=self)
            return

        def require_clean_repo_general(
            git_repo: git.Repo = None, ignore_pattern: list = None
        ) -> bool:

            if git_repo is None:
                git_repo = git.Repo(self.REVIEW_MANAGER.path)

            # Note : not considering untracked files.

            if len(git_repo.index.diff("HEAD")) == 0:
                unstaged_changes = [item.a_path for item in git_repo.index.diff(None)]
                if (
                    self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]
                    in unstaged_changes
                ):
                    git_repo.index.add(
                        [self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]]
                    )
                if self.REVIEW_MANAGER.paths["PAPER_RELATIVE"] in unstaged_changes:
                    git_repo.index.add([self.REVIEW_MANAGER.paths["PAPER_RELATIVE"]])

            # Principle: working tree always has to be clean
            # because processing functions may change content
            if git_repo.is_dirty(index=False):
                changedFiles = [item.a_path for item in git_repo.index.diff(None)]
                raise UnstagedGitChangesError(changedFiles)

            if git_repo.is_dirty():
                if ignore_pattern is None:
                    changedFiles = [
                        item.a_path for item in git_repo.index.diff(None)
                    ] + [
                        x.a_path
                        for x in git_repo.head.commit.diff()
                        if x.a_path
                        not in [str(self.REVIEW_MANAGER.paths["STATUS_RELATIVE"])]
                    ]
                    if len(changedFiles) > 0:
                        raise CleanRepoRequiredError(changedFiles, "")
                else:
                    changedFiles = [
                        item.a_path
                        for item in git_repo.index.diff(None)
                        if not any(str(ip) in item.a_path for ip in ignore_pattern)
                    ] + [
                        x.a_path
                        for x in git_repo.head.commit.diff()
                        if not any(str(ip) in x.a_path for ip in ignore_pattern)
                    ]
                    if (
                        str(self.REVIEW_MANAGER.paths["STATUS_RELATIVE"])
                        in changedFiles
                    ):
                        changedFiles.remove(
                            str(self.REVIEW_MANAGER.paths["STATUS_RELATIVE"])
                        )
                    if changedFiles:
                        raise CleanRepoRequiredError(
                            changedFiles, ",".join([str(x) for x in ignore_pattern])
                        )
            return True

        if ProcessType.load == self.type:
            require_clean_repo_general(
                ignore_pattern=[
                    self.REVIEW_MANAGER.paths["SEARCHDIR_RELATIVE"],
                    self.REVIEW_MANAGER.paths["SETTINGS_RELATIVE"],
                ]
            )
            check_process_model_precondition()

        elif ProcessType.prep == self.type:

            if self.notify_state_transition_process:
                require_clean_repo_general()
                check_process_model_precondition()

        elif ProcessType.prep_man == self.type:
            require_clean_repo_general(
                ignore_pattern=[self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]]
            )
            check_process_model_precondition()

        elif ProcessType.dedupe == self.type:
            require_clean_repo_general()
            check_process_model_precondition()

        elif ProcessType.prescreen == self.type:
            require_clean_repo_general(
                ignore_pattern=[self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]]
            )
            check_process_model_precondition()

        elif ProcessType.pdf_get == self.type:
            require_clean_repo_general(
                ignore_pattern=[self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]]
            )
            check_process_model_precondition()

        elif ProcessType.pdf_get_man == self.type:
            require_clean_repo_general(
                ignore_pattern=[self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]]
            )
            check_process_model_precondition()

        elif ProcessType.pdf_prep == self.type:
            require_clean_repo_general()
            check_process_model_precondition()

        elif ProcessType.pdf_prep_man == self.type:
            # require_clean_repo_general(
            #     ignore_pattern=[self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]]
            # )
            # check_process_model_precondition()
            pass

        elif ProcessType.screen == self.type:
            require_clean_repo_general()
            check_process_model_precondition()

        elif ProcessType.data == self.type:
            require_clean_repo_general(
                ignore_pattern=[
                    self.REVIEW_MANAGER.paths["PAPER_RELATIVE"],
                    self.REVIEW_MANAGER.paths["DATA_RELATIVE"],
                ]
            )
            check_process_model_precondition()

        elif ProcessType.format == self.type:
            pass
        elif ProcessType.explore == self.type:
            pass
        elif ProcessType.check == self.type:
            pass


class FormatProcess(Process):
    def __init__(self, *, REVIEW_MANAGER, notify: bool = True):
        super().__init__(REVIEW_MANAGER=REVIEW_MANAGER, type=ProcessType.format)
        if notify:
            self.REVIEW_MANAGER.notify(process=self)


class CheckProcess(Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.check,
            notify_state_transition_process=False,
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
    for state in list(RecordState)
]


class ProcessModel:

    transitions = transitions = [
        {
            "trigger": "load",
            "source": RecordState.md_retrieved,
            "dest": RecordState.md_imported,
        },
        {
            "trigger": "prep",
            "source": RecordState.md_imported,
            "dest": RecordState.md_needs_manual_preparation,
        },
        {
            "trigger": "prep",
            "source": RecordState.md_imported,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": "prep_man",
            "source": RecordState.md_needs_manual_preparation,
            "dest": RecordState.md_prepared,
        },
        {
            "trigger": "dedupe",
            "source": RecordState.md_prepared,
            "dest": RecordState.md_processed,
        },
        {
            "trigger": "prescreen",
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_excluded,
        },
        {
            "trigger": "prescreen",
            "source": RecordState.md_processed,
            "dest": RecordState.rev_prescreen_included,
        },
        {
            "trigger": "pdf_get",
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": "pdf_get",
            "source": RecordState.rev_prescreen_included,
            "dest": RecordState.pdf_needs_manual_retrieval,
        },
        {
            "trigger": "pdf_get_man",
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_not_available,
        },
        {
            "trigger": "pdf_get_man",
            "source": RecordState.pdf_needs_manual_retrieval,
            "dest": RecordState.pdf_imported,
        },
        {
            "trigger": "pdf_prep",
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_needs_manual_preparation,
        },
        {
            "trigger": "pdf_prep",
            "source": RecordState.pdf_imported,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": "pdf_prep_man",
            "source": RecordState.pdf_needs_manual_preparation,
            "dest": RecordState.pdf_prepared,
        },
        {
            "trigger": "screen",
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_excluded,
        },
        {
            "trigger": "screen",
            "source": RecordState.pdf_prepared,
            "dest": RecordState.rev_included,
        },
        {
            "trigger": "data",
            "source": RecordState.rev_included,
            "dest": RecordState.rev_synthesized,
        },
    ]

    transitions_non_processing = [
        item for sublist in non_processing_transitions for item in sublist
    ]

    def __init__(
        self, *, state: str = None, process: ProcessType = None, REVIEW_MANAGER=None
    ):

        import logging

        if process is not None:
            start_states: typing.List[str] = [
                str(x["source"])
                for x in self.transitions
                if str(process) == x["trigger"]
            ]
            self.state = start_states[0]
        elif state is not None:
            self.state = state
        else:
            print("ERROR: no process or state provided")

        if REVIEW_MANAGER is not None:
            self.REVIEW_MANAGER = REVIEW_MANAGER

        logging.getLogger("transitions").setLevel(logging.WARNING)

        self.machine = Machine(
            model=self,
            states=RecordState,
            transitions=self.transitions + self.transitions_non_processing,
            initial=self.state,
        )

    def get_valid_transitions(self) -> list:
        return list(
            {x["trigger"] for x in self.transitions if x["source"] == self.state}
        )

    def get_preceding_states(self, *, state) -> set:
        preceding_states: typing.Set[RecordState] = set()
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

        if "True" == self.REVIEW_MANAGER.settings.project.delay_automated_processing:
            cur_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_states_set()
            self.REVIEW_MANAGER.logger.debug(f"cur_state_list: {cur_state_list}")
            self.REVIEW_MANAGER.logger.debug(f"precondition: {self.state}")
            required_absent = {
                str(x) for x in self.get_preceding_states(state=self.state)
            }
            self.REVIEW_MANAGER.logger.debug(f"required_absent: {required_absent}")
            intersection = cur_state_list.intersection(required_absent)
            if (
                len(cur_state_list) == 0
                and not process.type.name == "load"  # type: ignore
            ):
                raise NoRecordsError()
            if len(intersection) != 0:
                raise ProcessOrderViolation(process, self.state, intersection)
        return


class SearchEndpoint(zope.interface.Interface):

    source_identifier = zope.interface.Attribute("""Source identifier""")
    mode = zope.interface.Attribute("""Mode""")

    def run_search(SEARCH, params: dict, feed_file: Path) -> None:
        pass

    def validate_params(query: str) -> None:
        pass


class SearchSourceEndpoint(zope.interface.Interface):

    source_identifier = zope.interface.Attribute("""Source identifier for provenance""")

    def heuristic(filename, data):
        pass

    def prepare(RECORD):
        pass


class LoadEndpoint(zope.interface.Interface):

    supported_extensions = zope.interface.Attribute("""List of supported extensions""")

    def load(LOADER, SOURCE):
        pass


class PreparationEndpoint(zope.interface.Interface):

    source_correction_hint = zope.interface.Attribute(
        """Hint on how to correct metadata at source"""
    )

    always_apply_changes = zope.interface.Attribute(
        """Flag indicating whether changes should always be applied
        (even if the colrev_status does not transition to md_prepared)"""
    )

    def prepare(PREPARATION, PREP_RECORD):
        pass


class PreparationManualEndpoint(zope.interface.Interface):
    def prepare_manual(PREP_MAN, records):
        pass


class DedupeEndpoint(zope.interface.Interface):
    def run_dedupe(DEDUPE):
        pass


class PrescreenEndpoint(zope.interface.Interface):
    def run_prescreen(PRESCREEN, records: dict, split: list) -> dict:
        pass


class PDFRetrievalEndpoint(zope.interface.Interface):
    def get_pdf(PDF_RETRIEVAL, RECORD):
        return RECORD


class PDFRetrievalManualEndpoint(zope.interface.Interface):
    def get_man_pdf(PDF_RETRIEVAL_MAN, records):
        return records


class PDFPreparationEndpoint(zope.interface.Interface):
    def prep_pdf(PDF_PREPARATION, RECORD, PAD) -> dict:
        return RECORD.data


class PDFPreparationManualEndpoint(zope.interface.Interface):
    def prep_man_pdf(PDF_PREP_MAN, records):
        return records


class ScreenEndpoint(zope.interface.Interface):
    def run_screen(SCREEN, records: dict, split: list) -> dict:
        pass


class DataEndpoint(zope.interface.Interface):
    def get_default_setup() -> dict:  # type: ignore
        return {}

    def update_data(
        DATA, records: dict, synthesized_record_status_matrix: dict
    ) -> None:
        pass

    def update_record_status_matrix(
        DATA, synthesized_record_status_matrix, endpoint_identifier
    ) -> None:
        pass


@dataclass
class DefaultSettings:
    name: str


if __name__ == "__main__":
    pass
