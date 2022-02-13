#!/usr/bin/env python3
import typing
from enum import auto
from enum import Enum

import git
from transitions import Machine


class ProcessType(Enum):
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


class RecordState(Enum):
    # without the md_retrieved state, we could not display the load transition
    md_retrieved = auto()
    md_imported = auto()
    md_needs_manual_preparation = auto()
    md_prepared = auto()
    md_processed = auto()
    rev_prescreen_excluded = auto()
    rev_prescreen_included = auto()
    pdf_needs_manual_retrieval = auto()
    pdf_imported = auto()
    pdf_not_available = auto()
    pdf_needs_manual_preparation = auto()
    pdf_prepared = auto()
    rev_excluded = auto()
    rev_included = auto()
    rev_synthesized = auto()
    # Note : TBD: rev_coded

    def __str__(self):
        return f"{self.name}"


class Process:
    def __init__(
        self,
        type: ProcessType,
        fun=None,
    ):
        from colrev_core.review_manager import ReviewManager

        self.REVIEW_MANAGER = ReviewManager()

        self.EMAIL = self.REVIEW_MANAGER.config["EMAIL"]
        self.DEBUG_MODE = self.REVIEW_MANAGER.config["DEBUG_MODE"]
        self.CPUS = self.REVIEW_MANAGER.config["CPUS"]

        self.type = type
        if fun is None:
            self.interactive = True
        else:
            self.interactive = False
        self.processing_function = fun

        self.logger = self.REVIEW_MANAGER.logger
        self.report_logger = self.REVIEW_MANAGER.report_logger
        self.pp = self.REVIEW_MANAGER.pp
        self.logger.debug(f"Created {self.type} process")

        # Note: we call REVIEW_MANAGER.notify() in the subclasses
        # to make sure that the REVIEW_MANAGER calls the right check_preconditions()

    def get_source_state(process):
        if any([x["trigger"] == process.type.name for x in ProcessModel.transitions]):
            source_state = [
                x["source"]
                for x in ProcessModel.transitions
                if x["trigger"] == process.type.name
            ]
            return source_state[0]
        elif any(
            [
                x["trigger"] == process.type.name
                for x in ProcessModel.transitions_non_processing
            ]
        ):
            source_state = [
                x["source"]
                for x in ProcessModel.transitions_non_processing
                if x["trigger"] == process.type.name
            ]
            return source_state[0]

    def run_process(self, *args):
        self.processing_function(*args)

    # Note: process subtypes will override this function
    def check_precondition(self) -> None:
        raise NotImplementedError()

    def check_process_model_precondition(self) -> None:
        PROCESS_MODEL = ProcessModel(
            process=self.type, REVIEW_MANAGER=self.REVIEW_MANAGER
        )
        PROCESS_MODEL.check_process_precondition(self)
        return

    def require_clean_repo_general(
        self, git_repo: git.Repo = None, ignore_pattern: list = None
    ) -> bool:

        # TODO: we may want to be more specific,
        # i.e.,allow staged/unstaged changes (e.g., in readme.md, ...)
        # TBD : require changes in .pre-commit-config.yaml to be in a separate commit?

        if git_repo is None:
            git_repo = git.Repo()

        # Note : not considering untracked files.

        if len(git_repo.index.diff("HEAD")) == 0:
            unstaged_changes = [item.a_path for item in git_repo.index.diff(None)]
            if (
                self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
                in unstaged_changes
            ):
                git_repo.index.add(
                    [self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]]
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
                changedFiles = [item.a_path for item in git_repo.index.diff(None)] + [
                    x.a_path
                    for x in git_repo.head.commit.diff()
                    if x.a_path not in ["status.yaml"]
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
                if "status.yaml" in changedFiles:
                    changedFiles.remove("status.yaml")
                if changedFiles:
                    raise CleanRepoRequiredError(
                        changedFiles, ",".join([str(x) for x in ignore_pattern])
                    )
        return True


class LoadProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.load, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general(
            ignore_pattern=[
                self.REVIEW_MANAGER.paths["SEARCHDIR_RELATIVE"],
                self.REVIEW_MANAGER.paths["SOURCES_RELATIVE"],
            ]
        )
        super().check_process_model_precondition()
        return


class PrepProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        self.notify = notify
        super().__init__(ProcessType.prep, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        if self.notify:
            super().require_clean_repo_general()
            super().check_process_model_precondition()
        return


class PrepManProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.prep_man, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general(
            ignore_pattern=[self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]]
        )
        super().check_process_model_precondition()
        return


class DedupeProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.dedupe, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general()
        super().check_process_model_precondition()
        return


class PrescreenProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.prescreen, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:

        super().require_clean_repo_general(
            ignore_pattern=[self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]]
        )
        super().check_process_model_precondition()
        return


class PDFRetrievalProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.pdf_get, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general(
            ignore_pattern=[self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]]
        )
        super().check_process_model_precondition()
        return


class PDFManualRetrievalProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.pdf_get_man, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general(
            ignore_pattern=[self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]]
        )
        super().check_process_model_precondition()
        return


class PDFPreparationProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.pdf_prep, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general()
        super().check_process_model_precondition()
        return


class PDFManualPreparationProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.pdf_prep_man, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general(
            ignore_pattern=[self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]]
        )
        super().check_process_model_precondition()
        return


class ScreenProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.screen, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general()
        super().check_process_model_precondition()
        return


class DataProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        self.notify = notify
        super().__init__(ProcessType.data, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        super().require_clean_repo_general(
            ignore_pattern=[self.REVIEW_MANAGER.paths["PAPER_RELATIVE"]]
        )
        super().check_process_model_precondition()
        return


class FormatProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.format, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        return


class CheckProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.check, fun)
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        return


class ExploreProcess(Process):
    def __init__(self, fun=None, notify: bool = True):
        super().__init__(ProcessType.explore, fun)

        self.notify = notify
        if notify:
            self.REVIEW_MANAGER.notify(self)

    def check_precondition(self) -> None:
        return


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


# TODO : check_process_model_precondition should be done
# by reviewmanager based on processmodel (previously record)
# -> really?!?!?


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
        self, state: str = None, process: ProcessType = None, REVIEW_MANAGER=None
    ):

        import logging

        if process is not None:
            start_states: typing.List[str] = [
                str(x["source"])
                for x in self.transitions
                if str(process) == x["trigger"]
            ]
            # TODO: check whether start_states are all the same
            self.state = start_states.pop()
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

    def get_preceding_states(self, state) -> set:
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

    def check_process_precondition(self, process: Process) -> None:
        cur_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_states_set()
        self.REVIEW_MANAGER.logger.debug(f"cur_state_list: {cur_state_list}")
        if self.REVIEW_MANAGER.config["DELAY_AUTOMATED_PROCESSING"]:
            self.REVIEW_MANAGER.logger.debug(f"precondition: {self.state}")
            required_absent = {str(x) for x in self.get_preceding_states(self.state)}
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


class NoRecordsError(Exception):
    def __init__(self):
        self.message = "no records imported yet"
        super().__init__(self.message)


class UnstagedGitChangesError(Exception):
    def __init__(self, changedFiles):
        self.message = (
            f"changes not yet staged: {changedFiles} (use git add . or stash)"
        )
        super().__init__(self.message)


class CleanRepoRequiredError(Exception):
    def __init__(self, changedFiles, ignore_pattern):
        self.message = (
            "clean repository required (use git commit, discard or stash "
            + f"{changedFiles}; ignore_pattern={ignore_pattern})."
        )
        super().__init__(self.message)


class ProcessOrderViolation(Exception):
    def __init__(self, process, required_state: str, violating_records: list):
        self.message = (
            f" {process.type.name}() requires all records to have at least "
            + f"'{required_state}', but there are records with {violating_records}."
        )
        super().__init__(self.message)


if __name__ == "__main__":
    pass
