#!/usr/bin/env python3
import logging
import pprint
import typing
from enum import auto
from enum import Enum

import git
from transitions import Machine


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


non_processing_transitions = [
    [
        {
            "trigger": "format",
            "source": state,
            "dest": state,
            "conditions": ["clean_repo_except_main_references"],
        },
        {
            "trigger": "explore",
            "source": state,
            "dest": state,
            "conditions": ["clean_repo_except_main_references"],
        },
        {
            "trigger": "check",
            "source": state,
            "dest": state,
            "conditions": [],
        },
    ]
    for state in list(RecordState)
]


# Note : conditions are defined in Record class
processing_transitions = [
    {
        "trigger": "load",
        "source": RecordState.md_retrieved,
        "dest": RecordState.md_imported,
        "conditions": ["clean_repo_except_search"],
    },
    {
        "trigger": "prep",
        "source": RecordState.md_imported,
        "dest": RecordState.md_needs_manual_preparation,
        "conditions": ["clean_repo", "check_records_state_precondition"],
    },
    {
        "trigger": "prep",
        "source": RecordState.md_imported,
        "dest": RecordState.md_prepared,
        "conditions": ["clean_repo", "check_records_state_precondition"],
    },
    {
        "trigger": "prep_man",
        "source": RecordState.md_needs_manual_preparation,
        "dest": RecordState.md_prepared,
        "conditions": [
            "clean_repo_except_main_references",
            "check_records_state_precondition",
        ],
    },
    {
        "trigger": "dedupe",
        "source": RecordState.md_prepared,
        "dest": RecordState.md_processed,
        "conditions": ["clean_repo", "check_records_state_precondition"],
    },
    {
        "trigger": "prescreen",
        "source": RecordState.md_processed,
        "dest": RecordState.rev_prescreen_excluded,
        "conditions": [
            "clean_repo_except_main_references",
            "check_records_state_precondition",
        ],
    },
    {
        "trigger": "prescreen",
        "source": RecordState.md_processed,
        "dest": RecordState.rev_prescreen_included,
        "conditions": [
            "clean_repo_except_main_references",
            "check_records_state_precondition",
        ],
    },
    {
        "trigger": "pdf_get",
        "source": RecordState.rev_prescreen_included,
        "dest": RecordState.pdf_imported,
        "conditions": [
            "clean_repo_except_pdf_dir",
            "check_records_state_precondition",
        ],
    },
    {
        "trigger": "pdf_get",
        "source": RecordState.rev_prescreen_included,
        "dest": RecordState.pdf_needs_manual_retrieval,
        "conditions": [
            "clean_repo_except_pdf_dir",
            "check_records_state_precondition",
        ],
    },
    {
        "trigger": "pdf_get_man",
        "source": RecordState.pdf_needs_manual_retrieval,
        "dest": RecordState.pdf_not_available,
        "conditions": [
            "clean_repo_except_pdf_dir_and_main_refs",
            "check_records_state_precondition",
        ],
    },
    {
        "trigger": "pdf_get_man",
        "source": RecordState.pdf_needs_manual_retrieval,
        "dest": RecordState.pdf_imported,
        "conditions": [
            "clean_repo_except_pdf_dir_and_main_refs",
            "check_records_state_precondition",
        ],
    },
    {
        "trigger": "pdf_prep",
        "source": RecordState.pdf_imported,
        "dest": RecordState.pdf_needs_manual_preparation,
        "conditions": ["clean_repo", "check_records_state_precondition"],
    },
    {
        "trigger": "pdf_prep",
        "source": RecordState.pdf_imported,
        "dest": RecordState.pdf_prepared,
        "conditions": ["clean_repo", "check_records_state_precondition"],
    },
    {
        "trigger": "pdf_prep_man",
        "source": RecordState.pdf_needs_manual_preparation,
        "dest": RecordState.pdf_prepared,
        "conditions": [
            "clean_repo_except_pdf_dir_and_main_refs",
            "check_records_state_precondition",
        ],
    },
    {
        "trigger": "screen",
        "source": RecordState.pdf_prepared,
        "dest": RecordState.rev_excluded,
        "conditions": ["clean_repo", "check_records_state_precondition"],
    },
    {
        "trigger": "screen",
        "source": RecordState.pdf_prepared,
        "dest": RecordState.rev_included,
        "conditions": ["clean_repo", "check_records_state_precondition"],
    },
    {
        "trigger": "data",
        "source": RecordState.rev_included,
        "dest": RecordState.rev_synthesized,
        "conditions": [
            "clean_repo_except_manuscript",
            "check_records_state_precondition",
        ],
    },
]


class Record:

    transitions = processing_transitions
    transitions_non_processing = [
        item for sublist in non_processing_transitions for item in sublist
    ]

    def __init__(self, ID, start_state, REVIEW_MANAGER=None):
        self.ID = ID
        self.state = start_state
        if REVIEW_MANAGER is not None:
            self.REVIEW_MANAGER = REVIEW_MANAGER

        logging.getLogger("transitions").setLevel(logging.WARNING)

        self.machine = Machine(
            model=self,
            states=RecordState,
            transitions=self.transitions + self.transitions_non_processing,
            initial=start_state,
        )

    def get_valid_transitions(self) -> list:
        return list(
            {x["trigger"] for x in self.transitions if x["source"] == self.state}
        )

    @property
    def check_records_state_precondition(self) -> None:
        possible_transitions: typing.List[str] = [
            str(x["trigger"]) for x in self.transitions if self.state == x["source"]
        ]
        for possible_transition in possible_transitions:
            if self.REVIEW_MANAGER.config["DELAY_AUTOMATED_PROCESSING"]:
                logging.debug(f"precondition: {self.state}")
                process = Process(ProcessType[possible_transition])
                required_absent = process.get_preceding_states(self.state)
                logging.debug(f"required_absent: {required_absent}")
                cur_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_states_set()
                logging.debug(f"cur_state_list: {cur_state_list}")
                intersection = cur_state_list.intersection(required_absent)
                if (
                    len(cur_state_list) == 0
                    and not process.type.name == "load"  # type: ignore
                ):
                    raise NoRecordsError()
                if len(intersection) != 0:
                    raise ProcessOrderViolation(process, self.state, intersection)
        return

    @property
    def clean_repo(self) -> bool:
        return self.require_clean_repo_general()

    @property
    def clean_repo_except_search(self) -> bool:
        # TODO : this is a temporary fix
        return self.require_clean_repo_general(
            ignore_pattern=["search/", "sources.yaml"]
        )

    @property
    def clean_repo_except_main_references(self) -> bool:
        MAIN_REFERENCES = "references.bib"  # TODO : this is a temporary fix
        return self.require_clean_repo_general(ignore_pattern=[MAIN_REFERENCES])

    @property
    def clean_repo_except_pdf_dir(self) -> bool:
        PDF_DIRECTORY = "pdfs/"  # TODO : this is a temporary fix
        return self.require_clean_repo_general(ignore_pattern=[PDF_DIRECTORY])

    @property
    def clean_repo_except_pdf_dir_and_main_refs(self) -> bool:
        # TODO
        # PDF_DIRECTORY = "pdfs/"  # TODO : this is a temporary fix
        # return require_clean_repo_general(ignore_pattern=[PDF_DIRECTORY])
        return True

    @property
    def clean_repo_except_manuscript(self) -> bool:
        PAPER = "paper.md"  # TODO : this is a temporary fix
        return self.require_clean_repo_general(ignore_pattern=[PAPER])

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
            if "references.bib" in unstaged_changes:  # TODO : this is a temporary fix
                git_repo.index.add(["references.bib"])  # TODO : this is a temporary fix
            if "paper.md" in unstaged_changes:
                git_repo.index.add(["paper.md"])  # TODO : this is a temporary fix

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
                    if not any(ip in item.a_path for ip in ignore_pattern)
                ] + [
                    x.a_path
                    for x in git_repo.head.commit.diff()
                    if not any(ip in x.a_path for ip in ignore_pattern)
                ]
                if "status.yaml" in changedFiles:
                    changedFiles.remove("status.yaml")
                if changedFiles:
                    raise CleanRepoRequiredError(changedFiles, ",".join(ignore_pattern))
        return True


class Process:
    pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)
    report_logger = logging.getLogger("colrev_core_report")
    logger = logging.getLogger("colrev_core")

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

    def get_source_state(process):
        if any([x["trigger"] == process.type.name for x in Record.transitions]):
            source_state = [
                x["source"]
                for x in Record.transitions
                if x["trigger"] == process.type.name
            ]
            return source_state[0]
        elif any(
            [
                x["trigger"] == process.type.name
                for x in Record.transitions_non_processing
            ]
        ):
            source_state = [
                x["source"]
                for x in Record.transitions_non_processing
                if x["trigger"] == process.type.name
            ]
            return source_state[0]

    def get_preceding_states(self, state) -> set:
        preceding_states: typing.Set[RecordState] = set()
        added = True
        while added:
            preceding_states_size = len(preceding_states)
            for transition in Record.transitions:
                if (
                    transition["dest"] in preceding_states
                    or state == transition["dest"]
                ):
                    preceding_states.add(transition["source"])  # type: ignore
            if preceding_states_size == len(preceding_states):
                added = False
        return preceding_states

    def run_process(self, *args):
        self.processing_function(*args)

    # def format_transition(start_state: str, end_state: str) -> str:
    #     transition = f"{start_state}>{end_state}"
    #     if start_state == end_state:
    #         transition = "-"
    #     return transition


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
    def __init__(self, process, required_states: set, violating_records: list):
        self.message = (
            f" {process.type.name}() requires all records to have at least "
            + f"'{required_states}', but there are records with {violating_records}."
        )
        super().__init__(self.message)


if __name__ == "__main__":
    pass
