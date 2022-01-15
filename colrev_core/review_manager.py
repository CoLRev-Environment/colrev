#!/usr/bin/env python3
import ast
import configparser
import errno
import importlib
import inspect
import io
import itertools
import json
import logging
import multiprocessing as mp
import os
import pkgutil
import pprint
import re
import string
import subprocess
import sys
import tempfile
import typing
import unicodedata
from contextlib import redirect_stdout
from enum import auto
from enum import Enum
from importlib.metadata import version
from pathlib import Path

import bibtexparser
import git
import pandas as pd
import yaml
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode
from transitions import Machine
from yaml import safe_load

import docker
from colrev_core import screen

logging.getLogger("transitions").setLevel(logging.WARNING)

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


###############################################################################


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


def get_bibtex_writer() -> BibTexWriter:

    writer = BibTexWriter()

    writer.contents = ["entries"]
    # Note: IDs should be at the beginning to facilitate git versioning
    # order: hard-coded in get_record_status_item()
    writer.display_order = [
        "origin",  # must be in second line
        "status",  # must be in third line
        "metadata_source",
        "excl_criteria",
        "man_prep_hints",
        "pdf_processed",
        "file",  # Note : do not change this order (parsers rely on it)
        "pdf_hash",
        "potential_dupes",
        "doi",
        "grobid-version",
        "dblp_key",
        "author",
        "booktitle",
        "journal",
        "title",
        "year",
        "editor",
        "number",
        "pages",
        "series",
        "volume",
        "abstract",
        "book-author",
        "book-group-author",
    ]

    writer.order_entries_by = "ID"
    writer.add_trailing_comma = True
    writer.align_values = True
    writer.indent = "  "
    return writer


def get_file_paths(repository_dir_str: str) -> dict:
    repository_dir = Path(repository_dir_str)
    main_refs = "references.bib"
    data = "data.yaml"
    pdf_dir = "pdfs"
    sources = "sources.yaml"
    paper = "paper.md"
    shared_config = "shared_config.ini"
    private_config = "private_config.ini"
    readme = "readme.md"
    report = "report.log"
    search_dir = "search"
    local_registry = ".colrev.yaml"
    return {
        "REPO_DIR": repository_dir,
        "MAIN_REFERENCES_RELATIVE": Path(main_refs),
        "MAIN_REFERENCES": repository_dir.joinpath(main_refs),
        "DATA_RELATIVE": Path(data),
        "DATA": repository_dir.joinpath(data),
        "PDF_DIRECTORY_RELATIVE": Path(pdf_dir),
        "PDF_DIRECTORY": repository_dir.joinpath(pdf_dir),
        "SOURCES_RELATIVE": Path(sources),
        "SOURCES": repository_dir.joinpath(sources),
        "PAPER_RELATIVE": Path(paper),
        "PAPER": repository_dir.joinpath(paper),
        "SHARED_CONFIG_RELATIVE": Path(shared_config),
        "SHARED_CONFIG": repository_dir.joinpath(shared_config),
        "PRIVATE_CONFIG_RELATIVE": Path(private_config),
        "PRIVATE_CONFIG": repository_dir.joinpath(private_config),
        "README_RELATIVE": Path(readme),
        "README": repository_dir.joinpath(readme),
        "REPORT_RELATIVE": Path(report),
        "REPORT": repository_dir.joinpath(report),
        "SEARCHDIR_RELATIVE": Path(search_dir),
        "SEARCHDIR": repository_dir.joinpath(search_dir),
        "LOCAL_REGISTRY": Path.home().joinpath(local_registry),
    }


def setup_logger(level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger("colrev_core")

    if not logger.handlers:
        logger.setLevel(level)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.propagate = False
    return logger


def setup_report_logger(level=logging.INFO) -> logging.Logger:

    report_logger = logging.getLogger("colrev_core_report")

    if not report_logger.handlers:
        report_logger.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        report_file_handler = logging.FileHandler("report.log", mode="a")
        report_file_handler.setFormatter(formatter)

        report_logger.addHandler(report_file_handler)
        if logging.DEBUG == level:
            report_logger.addHandler(handler)
        report_logger.propagate = False

    return report_logger


###############################################################################


class MissingDependencyError(Exception):
    def __init__(self, dep):
        self.message = f"please install {dep}"
        super().__init__(self.message)


class SoftwareUpgradeError(Exception):
    def __init__(self, old, new):
        self.message = (
            f"Detected upgrade from {old} to {new}. Please use XXX to upgreade."
        )
        super().__init__(self.message)


class GitConflictError(Exception):
    def __init__(self, path):
        self.message = f"please resolve git conflict in {path}"
        super().__init__(self.message)


class StatusFieldValueError(Exception):
    def __init__(self, record: str, status_type: str, status_value: str):
        self.message = f"{status_type} set to '{status_value}' in {record}."
        super().__init__(self.message)


class CitationKeyPropagationError(Exception):
    pass


class DirtyRepoAfterProcessingError(Exception):
    pass


class ReviewManagerNotNofiedError(Exception):
    def __init__(self):
        self.message = (
            "inform the review manager about the next process in advance"
            + " to avoid conflicts (run review_manager.notify(processing_function))"
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


class ConsistencyError(Exception):
    pass


class RepoSetupError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class DuplicatesError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class RecordFormatError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class OriginError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class FieldError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class StatusTransitionError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class ManuscriptRecordSourceTagError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class PropagatedIDChange(Exception):
    def __init__(self, notifications):
        self.message = "\n".join(notifications)
        super().__init__(self.message)


class SearchDetailsMissingError(Exception):
    def __init__(
        self,
        search_results_path,
    ):
        self.message = (
            "Search results path "
            + f"({search_results_path.name}) "
            + "is not in sources.yaml"
        )
        super().__init__(self.message)


class SearchDetailsError(Exception):
    def __init__(
        self,
        msg,
    ):
        self.message = f" {msg}"
        super().__init__(self.message)


class RawSearchChangedError(Exception):
    def __init__(self, path):
        self.message = f"revert changes to raw search results: {path}"
        super().__init__(self.message)


###############################################################################


def rmdiacritics(char: str) -> str:
    """
    Return the base character of char, by "removing" any
    diacritics like accents or curls and strokes and the like.
    """
    desc = unicodedata.name(char)
    cutoff = desc.find(" WITH ")
    if cutoff != -1:
        desc = desc[:cutoff]
        try:
            char = unicodedata.lookup(desc)
        except KeyError:
            pass  # removing "WITH ..." produced an invalid name
    return char


def remove_accents(input_str: str) -> str:
    try:
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        wo_ac_list = [
            rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)
        ]
        wo_ac = "".join(wo_ac_list)
    except ValueError:
        wo_ac = input_str
        pass
    return wo_ac


def inplace_change(filename: Path, old_string: str, new_string: str) -> None:
    with open(filename) as f:
        s = f.read()
        if old_string not in s:
            logging.info(f'"{old_string}" not found in {filename}.')
            return
    with open(filename, "w") as f:
        s = s.replace(old_string, new_string)
        f.write(s)
    return


def retrieve_package_file(template_file: Path, target: Path) -> None:
    filedata = pkgutil.get_data(__name__, str(template_file))
    if filedata:
        with open(target, "w") as file:
            file.write(filedata.decode("utf-8"))
    return


def check_git_installed() -> None:
    try:
        null = open("/dev/null", "w")
        subprocess.Popen("git", stdout=null, stderr=null)
        null.close()
    except OSError:
        pass
        raise MissingDependencyError("git")
    return


def check_docker_installed() -> None:
    try:
        null = open("/dev/null", "w")
        subprocess.Popen("docker", stdout=null, stderr=null)
        null.close()
    except OSError:
        pass
        raise MissingDependencyError("docker")
    return


def build_docker_images(self) -> None:

    client = docker.from_env()

    repo_tags = [x.attrs.get("RepoTags", "") for x in client.images.list()]
    repo_tags = [
        item[0][: item[0].find(":")]
        for item in [sublist for sublist in repo_tags if sublist is not None]
    ]

    if "bibutils" not in repo_tags:
        self.logger.info("Building bibutils Docker image...")
        filedata = pkgutil.get_data(__name__, "../docker/bibutils/Dockerfile")
        if filedata:
            fileobj = io.BytesIO(filedata)
            client.images.build(fileobj=fileobj, tag="bibutils:latest")
        else:
            self.logger.error("Cannot retrieve image bibutils")

    if "lfoppiano/grobid" not in repo_tags:
        self.logger.info("Pulling grobid Docker image...")
        client.images.pull("lfoppiano/grobid:0.7.0")
    if "pandoc/ubuntu-latex" not in repo_tags:
        self.logger.info("Pulling pandoc/ubuntu-latex image...")
        client.images.pull("pandoc/ubuntu-latex:2.14")
    if "jbarlow83/ocrmypdf" not in repo_tags:
        self.logger.info("Pulling jbarlow83/ocrmypdf image...")
        client.images.pull("pandoc/ubuntu-latex:latest")

    return


def get_base_prefix_compat() -> str:
    return (
        getattr(sys, "base_prefix", None)
        or getattr(sys, "real_prefix", None)
        or sys.prefix
    )


def in_virtualenv() -> bool:
    return get_base_prefix_compat() != sys.prefix


def check_git_conflicts(REVIEW_MANAGER) -> None:
    # Note: when check is called directly from the command line.
    # pre-commit hooks automatically notify on merge conflicts

    git_repo = git.Repo(str(REVIEW_MANAGER.paths["REPO_DIR"]))
    unmerged_blobs = git_repo.index.unmerged_blobs()

    for path in unmerged_blobs:
        list_of_blobs = unmerged_blobs[path]
        for (stage, blob) in list_of_blobs:
            if stage != 0:
                raise GitConflictError(path)
    return


def is_git_repo(path: Path) -> bool:
    from git.exc import InvalidGitRepositoryError

    try:
        _ = git.Repo(str(path)).git_dir
        return True
    except InvalidGitRepositoryError:
        return False


def is_colrev_core_project() -> bool:
    # Note : 'private_config.ini', 'shared_config.ini' are optional
    # "search",
    required_paths = [Path(".pre-commit-config.yaml"), Path(".gitignore")]
    if not all(x.is_file() for x in required_paths):
        return False
    return True


def get_installed_hooks() -> dict:
    installed_hooks: dict = {"hooks": list()}
    with open(".pre-commit-config.yaml") as pre_commit_y:
        pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)
    installed_hooks[
        "remote_pv_hooks_repo"
    ] = "https://github.com/geritwagner/colrev-hooks"
    for repository in pre_commit_config["repos"]:
        if repository["repo"] == installed_hooks["remote_pv_hooks_repo"]:
            installed_hooks["local_hooks_version"] = repository["rev"]
            installed_hooks["hooks"] = [hook["id"] for hook in repository["hooks"]]
    return installed_hooks


def lsremote(url: str) -> dict:
    remote_refs = {}
    g = git.cmd.Git()
    for ref in g.ls_remote(url).split("\n"):
        hash_ref_list = ref.split("\t")
        remote_refs[hash_ref_list[1]] = hash_ref_list[0]
    return remote_refs


def hooks_up_to_date(installed_hooks: dict) -> bool:
    refs = lsremote(installed_hooks["remote_pv_hooks_repo"])
    remote_sha = refs["HEAD"]
    if remote_sha == installed_hooks["local_hooks_version"]:
        return True
    return False


def require_hooks_installed(installed_hooks: dict) -> bool:
    required_hooks = ["check", "format", "report", "sharing"]
    hooks_activated = set(installed_hooks["hooks"]) == set(required_hooks)
    if not hooks_activated:
        missing_hooks = [x for x in required_hooks if x not in installed_hooks["hooks"]]
        raise RepoSetupError(
            f"missing hooks in .pre-commit-config.yaml ({missing_hooks})"
        )

    pch_file = Path(".git/hooks/pre-commit")
    if pch_file.is_file():
        with open(pch_file) as f:
            if "File generated by pre-commit" not in f.read(4096):
                raise RepoSetupError(
                    "pre-commit hooks not installed (use pre-commit install)"
                )
    else:
        raise RepoSetupError("pre-commit hooks not installed (use pre-commit install)")

    psh_file = Path(".git/hooks/pre-push")
    if psh_file.is_file():
        with open(psh_file) as f:
            if "File generated by pre-commit" not in f.read(4096):
                raise RepoSetupError(
                    "pre-commit push hooks not installed "
                    "(use pre-commit install --hook-type pre-push)"
                )
    else:
        raise RepoSetupError(
            "pre-commit push hooks not installed "
            "(use pre-commit install --hook-type pre-push)"
        )

    pcmh_file = Path(".git/hooks/prepare-commit-msg")
    if pcmh_file.is_file():
        with open(pcmh_file) as f:
            if "File generated by pre-commit" not in f.read(4096):
                raise RepoSetupError(
                    "pre-commit prepare-commit-msg hooks not installed "
                    "(use pre-commit install --hook-type prepare-commit-msg)"
                )
    else:
        raise RepoSetupError(
            "pre-commit prepare-commit-msg hooks not installed "
            "(use pre-commit install --hook-type prepare-commit-msg)"
        )

    return True


def check_software(REVIEW_MANAGER) -> None:
    git_repo = REVIEW_MANAGER.get_repo()
    master = git_repo.head.reference
    cmsg_lines = master.commit.message.split("\n")
    for cmsg_line in cmsg_lines[0:20]:
        if "- colrev_core:" in cmsg_line:
            last_colrev_core_version = cmsg_line[cmsg_line.find("version ") + 8 :]
            current_colrev_core_version = version("colrev_core")
            last_colrev_core_version == current_colrev_core_version
            # TODO : how to deal with different versions of colrev_core?
            # if last_colrev_core_version != current_colrev_core_version:
            #     raise SoftwareUpgradeError(
            #         last_colrev_core_version, last_colrev_core_version
            #     )

    return


def check_repository_setup(REVIEW_MANAGER) -> None:
    from git.exc import GitCommandError

    # 1. git repository?
    if not is_git_repo(REVIEW_MANAGER.paths["REPO_DIR"]):
        raise RepoSetupError("no git repository. Use colrev_core init")

    # 2. colrev_core project?
    if not is_colrev_core_project():
        raise RepoSetupError(
            "No colrev_core repository."
            + "To retrieve a shared repository, use colrev_core init."
            + "To initalize a new repository, "
            + "execute the command in an empty directory."
        )

    installed_hooks = get_installed_hooks()

    # 3. Pre-commit hooks installed?
    require_hooks_installed(installed_hooks)

    # 4. Pre-commit hooks up-to-date?
    try:
        if not hooks_up_to_date(installed_hooks):
            raise RepoSetupError(
                "Pre-commit hooks not up-to-date. "
                + "Use pre-commit autoupdate (--bleeding-edge)"
            )
            # This could also be a warning, but hooks should not change often.

    except GitCommandError:
        REVIEW_MANAGER.logger.warning(
            "No Internet connection, cannot check remote "
            "colrev-hooks repository for updates."
        )
    return


class Record:

    transitions = processing_transitions
    transitions_non_processing = [
        item for sublist in non_processing_transitions for item in sublist
    ]

    def __init__(self, ID, start_state, REVIEW_MANAGER=None):
        self.ID = ID
        if REVIEW_MANAGER is not None:
            self.REVIEW_MANAGER = REVIEW_MANAGER

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
                cur_state_list = self.REVIEW_MANAGER.get_states_set()
                logging.debug(f"cur_state_list: {cur_state_list}")
                intersection = cur_state_list.intersection(required_absent)
                if len(cur_state_list) == 0 and not process.type.name == "load":
                    raise NoRecordsError()
                if len(intersection) != 0:
                    raise ProcessOrderViolation(process, self.state, intersection)
        return

    @property
    def clean_repo(self) -> bool:
        return require_clean_repo_general()

    @property
    def clean_repo_except_search(self) -> bool:
        # TODO : this is a temporary fix
        return require_clean_repo_general(ignore_pattern=["search/", "sources.yaml"])

    @property
    def clean_repo_except_main_references(self) -> bool:
        MAIN_REFERENCES = "references.bib"  # TODO : this is a temporary fix
        return require_clean_repo_general(ignore_pattern=[MAIN_REFERENCES])

    @property
    def clean_repo_except_pdf_dir(self) -> bool:
        PDF_DIRECTORY = "pdfs/"  # TODO : this is a temporary fix
        return require_clean_repo_general(ignore_pattern=[PDF_DIRECTORY])

    @property
    def clean_repo_except_pdf_dir_and_main_refs(self) -> bool:
        # TODO
        # PDF_DIRECTORY = "pdfs/"  # TODO : this is a temporary fix
        # return require_clean_repo_general(ignore_pattern=[PDF_DIRECTORY])
        return True

    @property
    def clean_repo_except_manuscript(self) -> bool:
        PAPER = "paper.md"  # TODO : this is a temporary fix
        return require_clean_repo_general(ignore_pattern=[PAPER])


class Process:
    def __init__(
        self,
        type: ProcessType,
        fun=None,
    ):
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
                    preceding_states.add(transition["source"])
            if preceding_states_size == len(preceding_states):
                added = False
        return preceding_states

    def run(self, review_manager, *args):
        self.processing_function(review_manager, *args)


def get_record_status_item(r_header: str) -> list:
    rhlines = r_header.split("\n")
    rhl0, rhl1, rhl2 = (
        line[line.find("{") + 1 : line.rfind(",")] for line in rhlines[0:3]
    )
    ID = rhl0
    if "status" not in rhlines[2]:
        raise StatusFieldValueError(ID, "status", "NA")
    status = rhl2[:-1]  # to replace the trailing }
    return [ID, status]


def get_record_header_item(r_header: str) -> list:
    rhlines = r_header.split("\n")
    rhl0, rhl1, rhl2, rhl3, rhl4, rhl5, rhl6, rhl7 = (
        line[line.find("{") + 1 : line.rfind(",")] for line in rhlines[0:8]
    )
    ID = rhl0

    if "origin" not in rhlines[1]:
        raise RecordFormatError(f"{ID} has status=NA")
    origin = rhl1[:-1]  # to replace the trailing }

    if "status" not in rhlines[2]:
        raise StatusFieldValueError(ID, "status", "NA")
    status = rhl2[:-1]  # to replace the trailing }

    # excl_criteria can only be in line 4 (but it is optional)
    excl_criteria = ""
    if "excl_criteria" in rhlines[4]:
        excl_criteria = rhl4[:-1]  # to replace the trailing }

    # file is optional and could be in lines 4-7
    file = ""
    if "file" in rhlines[4]:
        file = rhl4[:-1]  # to replace the trailing }
    if "file" in rhlines[5]:
        file = rhl5[:-1]  # to replace the trailing }
    if "file" in rhlines[6]:
        file = rhl6[:-1]  # to replace the trailing }
    if "file" in rhlines[7]:
        file = rhl7[:-1]  # to replace the trailing }

    return [ID, origin, status, excl_criteria, file]


def get_name_mail_from_global_git_config() -> list:
    ggit_conf_path = Path.home() / Path(".gitconfig")
    global_conf_details = []
    if os.path.exists(ggit_conf_path):
        glob_git_conf = git.GitConfigParser([str(ggit_conf_path)], read_only=True)
        global_conf_details = [
            glob_git_conf.get("user", "name"),
            glob_git_conf.get("user", "email"),
        ]
    return global_conf_details


def actor_fallback() -> str:
    name = get_name_mail_from_global_git_config()[0]
    return name


def email_fallback() -> str:
    email = get_name_mail_from_global_git_config()[1]
    return email


def require_clean_repo_general(
    git_repo: git.Repo = None, ignore_pattern: list = None
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


def retrieve_IDs_from_bib(file_path: Path) -> list:
    assert file_path.suffix == ".bib"
    IDs = []
    with open(file_path) as f:
        line = f.readline()
        while line:
            if "@" in line[:5]:
                ID = line[line.find("{") + 1 : line.rfind(",")]
                IDs.append(ID.lstrip())
            line = f.readline()
    return IDs


def read_next_record(file_object) -> typing.Iterator[str]:
    data = ""
    first_record_processed = False
    while True:
        line = file_object.readline()
        if not line:
            break
        if line[:1] == "%" or line == "\n":
            continue
        if line[:1] != "@":
            data += line
        else:
            if first_record_processed:
                yield data
            else:
                first_record_processed = True
            data = line
    yield data


def format_transition(start_state: str, end_state: str) -> str:
    transition = f"{start_state}>{end_state}"
    if start_state == end_state:
        transition = "-"
    return transition


def retrieve_prior(REVIEW_MANAGER) -> dict:
    MAIN_REFERENCES_RELATIVE = REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
    git_repo = REVIEW_MANAGER.get_repo()
    revlist = (
        (
            commit.hexsha,
            (commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read(),
        )
        for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
    )
    prior: dict = {"status": [], "persisted_IDs": []}
    filecontents = list(revlist)[0][1]
    for record_string in read_next_record(io.StringIO(filecontents.decode("utf-8"))):

        ID, status, origin = "NA", "NA", "NA"
        for line in record_string.split("\n"):
            if "@" in line[:3]:
                ID = line[line.find("{") + 1 : line.rfind(",")]
            if "status" == line.lstrip()[:6]:
                status = line[line.find("{") + 1 : line.rfind("}")]
            if "origin" == line.strip()[:6]:
                origin = line[line.find("{") + 1 : line.rfind("}")]
        if "NA" != ID:
            for orig in origin.split(";"):
                prior["status"].append([orig, status])
                if str(RecordState.md_processed) == status:
                    prior["persisted_IDs"].append([orig, ID])

        else:
            logging.error(f"record without ID: {record_string}")
    return prior


def retrieve_data(prior: dict, MAIN_REFERENCES: str) -> dict:

    data: dict = {
        "missing_file": [],
        "pdf_not_exists": [],
        "status_fields": [],
        "status_transitions": [],
        "start_states": [],
        "exclusion_criteria_list": [],
        "IDs": [],
        "entries_without_origin": [],
        "record_links_in_bib": [],
        "persisted_IDs": [],
        "origin_list": [],
    }

    with open(MAIN_REFERENCES) as f:
        for record_string in read_next_record(f):
            ID, file, status, excl_crit, origin = (
                "NA",
                "NA",
                "NA",
                "not_set",
                "NA",
            )
            # TODO: this can be done more efficiently
            # because we fixed the order of the first rows.
            for line in record_string.split("\n"):
                if "@" in line[:3]:
                    ID = line[line.find("{") + 1 : line.rfind(",")]
                if "file" == line.lstrip()[:4]:
                    file = line[line.find("{") + 1 : line.rfind("}")]
                if "status" == line.lstrip()[:6]:
                    status = line[line.find("{") + 1 : line.rfind("}")]
                if "excl_criteria" == line.lstrip()[:13]:
                    excl_crit = line[line.find("{") + 1 : line.rfind("}")]
                if "origin" == line.strip()[:6]:
                    origin = line[line.find("{") + 1 : line.rfind("}")]

            if "NA" == ID:
                logging.error(f"Skipping record without ID: {record_string}")
                continue

            data["IDs"].append(ID)

            for org in origin.split(";"):
                data["origin_list"].append([ID, org])

            # TODO: determine succeeding states from state machine
            if status in [
                str(RecordState.md_processed),
                str(RecordState.rev_prescreen_excluded),
                str(RecordState.rev_prescreen_included),
                str(RecordState.pdf_needs_manual_retrieval),
                str(RecordState.pdf_imported),
                str(RecordState.pdf_not_available),
                str(RecordState.pdf_needs_manual_preparation),
                str(RecordState.pdf_prepared),
                str(RecordState.rev_excluded),
                str(RecordState.rev_included),
                str(RecordState.rev_synthesized),
            ]:
                for origin_part in origin.split(";"):
                    data["persisted_IDs"].append([origin_part, ID])

            if file != "NA":
                if not all(Path(f).is_file() for f in file.split(";")):
                    data["pdf_not_exists"].append(ID)

            if origin != "NA":
                for org in origin.split(";"):
                    data["record_links_in_bib"].append(org)
            else:
                data["entries_without_origin"].append(ID)

            data["status_fields"].append(status)

            # TODO: determine succeeding states from state machine
            # excluding pdf_not_available
            file_required_status = [
                str(RecordState.pdf_imported),
                str(RecordState.pdf_needs_manual_preparation),
                str(RecordState.pdf_prepared),
                str(RecordState.rev_excluded),
                str(RecordState.rev_included),
                str(RecordState.rev_synthesized),
            ]

            if (" file  " not in record_string) and (status in file_required_status):
                data["missing_file"].append(ID)

            if "not_set" != excl_crit:
                ec_case = [ID, status, excl_crit]
                data["exclusion_criteria_list"].append(ec_case)

            # TODO: the origins of an record could be in multiple status
            if "status" in prior:
                prior_status = [
                    stat for (org, stat) in prior["status"] if org in origin.split(";")
                ]
            else:
                prior_status = []

            status_transition = {}
            if len(prior_status) == 0:
                status_transition[ID] = "load"
            else:
                proc_transition_list: list = [
                    x["trigger"]
                    for x in Record.transitions
                    if str(x["source"]) == prior_status[0] and str(x["dest"]) == status
                ]
                if len(proc_transition_list) == 0 and prior_status[0] != status:
                    data["start_states"].append(prior_status[0])
                    if prior_status[0] not in [str(x) for x in RecordState]:
                        raise StatusFieldValueError(ID, "status", prior_status[0])
                    if status not in [str(x) for x in RecordState]:
                        raise StatusFieldValueError(ID, "status", status)

                    raise StatusTransitionError(
                        f"invalid state transition ({ID}):"
                        + f" {prior_status[0]} to {status}"
                    )
                if 0 == len(proc_transition_list):
                    status_transition[ID] = "load"
                else:
                    proc_transition = proc_transition_list.pop()
                    status_transition[ID] = proc_transition

            data["status_transitions"].append(status_transition)

    return data


def check_main_references_duplicates(data: dict) -> None:

    if not len(data["IDs"]) == len(set(data["IDs"])):
        duplicates = [ID for ID in data["IDs"] if data["IDs"].count(ID) > 1]
        if len(duplicates) > 20:
            raise DuplicatesError(
                f"Duplicates in MAIN_REFERENCES: ({','.join(duplicates[0:20])}, ...)"
            )
        else:
            raise DuplicatesError(
                f"Duplicates in MAIN_REFERENCES: {','.join(duplicates)}"
            )
    return


def check_main_references_origin(REVIEW_MANAGER, prior: dict, data: dict) -> None:
    # Check whether each record has an origin
    if not len(data["entries_without_origin"]) == 0:
        raise OriginError(
            f"Entries without origin: {', '.join(data['entries_without_origin'])}"
        )

    # Check for broken origins
    search_dir = REVIEW_MANAGER.paths["SEARCHDIR"]
    all_record_links = []
    for bib_file in search_dir.glob("*.bib"):
        search_IDs = retrieve_IDs_from_bib(bib_file)
        for x in search_IDs:
            all_record_links.append(bib_file.name + "/" + x)
    delta = set(data["record_links_in_bib"]) - set(all_record_links)
    if len(delta) > 0:
        raise OriginError(f"broken origins: {delta}")

    # Check for non-unique origins
    origins = [x[1] for x in data["origin_list"]]
    non_unique_origins = []
    for org in origins:
        if origins.count(org) > 1:
            non_unique_origins.append(org)
    if non_unique_origins:
        for ID, org in data["origin_list"]:
            if org in non_unique_origins:
                raise OriginError(f'Non-unique origin: origin="{org}"')

    # Check for removed origins
    # TODO !!!!
    # Raise an exception if origins were removed
    # prior_origins = [x[0] for x in prior['status']]
    # current_origins = [x[1] for x in data['origin_list']]
    # print(len(prior_origins))
    # print(len(current_origins))
    # print(set(prior_origins).difference(set(current_origins)))
    # print(set(current_origins).difference(set(prior_origins)))
    # print(pp.pformat(prior))
    # # print(pp.pformat(data))
    # input('stop')
    # for prior_origin, prior_id in prior["persisted_IDs"]:
    #     # TBD: notify if the origin no longer exists?
    #     for new_origin, new_id in data["persisted_IDs"]:
    #         if new_origin == prior_origin:
    #             if new_id != prior_id:
    #                 logging.error(
    #                     f"ID of processed record changed from {prior_id} to {new_id}"
    #                 )
    #                 check_propagated_IDs(prior_id, new_id)
    #                 STATUS = FAIL
    return


def check_main_references_status_fields(data: dict) -> None:
    # Check status fields
    status_schema = [str(x) for x in RecordState]
    stat_diff = set(data["status_fields"]).difference(status_schema)
    if stat_diff:
        raise FieldError(f"status field(s) {stat_diff} not in {status_schema}")
    return


def check_main_references_status_transitions(data: dict) -> None:
    if len(set(data["start_states"])) > 1:
        raise StatusTransitionError(
            "multiple transitions from different "
            f'start states ({set(data["start_states"])})'
        )
    return


def check_main_references_screen(data: dict) -> None:

    # Check screen
    # Note: consistency of inclusion_2=yes -> inclusion_1=yes
    # is implicitly ensured through status
    # (screen2-included/excluded implies prescreen included!)

    if data["exclusion_criteria_list"]:
        exclusion_criteria = data["exclusion_criteria_list"][0][2]
        if exclusion_criteria != "NA":
            criteria = screen.get_exclusion_criteria_from_str(exclusion_criteria)
            pattern = "=(yes|no);".join(criteria) + "=(yes|no)"
            pattern_inclusion = "=no;".join(criteria) + "=no"
        else:
            criteria = ["NA"]
            pattern = "^NA$"
            pattern_inclusion = "^NA$"
        for [ID, status, excl_crit] in data["exclusion_criteria_list"]:
            # print([ID, status, excl_crit])
            if not re.match(pattern, excl_crit):
                # Note: this should also catch cases of missing
                # exclusion criteria
                raise FieldError(
                    "Exclusion criteria field not matching "
                    f"pattern: {excl_crit} ({ID}; criteria: {criteria})"
                )

            elif str(RecordState.rev_excluded) == status:
                if ["NA"] == criteria:
                    if "NA" == excl_crit:
                        continue
                    else:
                        raise FieldError(f"excl_crit field not NA: {excl_crit}")

                if "=yes" not in excl_crit:
                    logging.error(f"criteria: {criteria}")
                    raise FieldError(
                        "Excluded record with no exclusion_criterion violated: "
                        f"{ID}, {status}, {excl_crit}"
                    )

            # Note: we don't have to consider the cases of
            # status=retrieved/prescreen_included/prescreen_excluded
            # because they would not have exclusion_criteria.
            else:
                if not re.match(pattern_inclusion, excl_crit):
                    raise FieldError(
                        "Included record with exclusion_criterion satisfied: "
                        f"{ID}, {status}, {excl_crit}"
                    )
    return


def check_main_references_files(data: dict) -> None:

    # Check pdf files
    if len(data["missing_file"]) > 0:
        raise FieldError(
            "record with status requiring a PDF file but missing "
            + f'the path (file = ...): {data["missing_file"]}'
        )

    if len(data["pdf_not_exists"]) > 0:
        raise FieldError(f'record with broken file link: {data["pdf_not_exists"]}')

    return


def check_new_record_source_tag(PAPER: Path) -> None:
    with open(PAPER) as f:
        for line in f:
            if "<!-- NEW_RECORD_SOURCE -->" in line:
                return
    raise ManuscriptRecordSourceTagError(
        f"Did not find <!-- NEW_RECORD_SOURCE --> tag in {PAPER}"
    )


def check_update_synthesized_status(REVIEW_MANAGER) -> None:
    from colrev_core import data

    records = REVIEW_MANAGER.load_records()
    data.update_synthesized_status(REVIEW_MANAGER, records)

    return


# def check_screen_data(screen, data):
#     # Check consistency: data -> inclusion_2
#     data_IDs = data['ID'].tolist()
#     screen_IDs = \
#         screen['ID'][screen['inclusion_2'] == 'yes'].tolist()
#     violations = [ID for ID in set(
#         data_IDs) if ID not in set(screen_IDs)]
#     if len(violations) != 0:
#         raise some error ('IDs in DATA not coded as inclusion_2=yes: ' +
#               f'{violations}')
#     return


# def check_duplicates_data(data):
#     # Check whether there are duplicate IDs in data.csv
#     if not data['ID'].is_unique:
#         raise some error (data[data.duplicated(['ID'])].ID.tolist())
#     return


# def check_id_integrity_data(data, IDs):
#     # Check consistency: all IDs in data.csv in references.bib
#     missing_IDs = [ID for
#                    ID in data['ID'].tolist()
#                    if ID not in IDs]
#     if not len(missing_IDs) == 0:
#         raise some error ('IDs in data.csv not in MAIN_REFERENCES: ' +
#               str(set(missing_IDs)))
#     return


def check_propagated_IDs(prior_id: str, new_id: str) -> list:

    ignore_patterns = [".git", "config.ini", "report.log", ".pre-commit-config.yaml"]

    text_formats = [".txt", ".csv", ".md", ".bib", ".yaml"]
    notifications = []
    for root, dirs, files in os.walk(os.getcwd(), topdown=False):
        for name in files:
            if any((x in name) or (x in root) for x in ignore_patterns):
                continue
            if prior_id in name:
                notifications.append(
                    f"Old ID ({prior_id}, changed to {new_id} in the "
                    f"MAIN_REFERENCES) found in filepath: {name}"
                )

            if not any(name.endswith(x) for x in text_formats):
                logging.debug(f"Skipping {name}")
                continue
            logging.debug(f"Checking {name}")
            if name.endswith(".bib"):
                retrieved_IDs = retrieve_IDs_from_bib(Path(os.path.join(root, name)))
                if prior_id in retrieved_IDs:
                    notifications.append(
                        f"Old ID ({prior_id}, changed to {new_id} in "
                        f"the MAIN_REFERENCES) found in file: {name}"
                    )
            else:
                with open(os.path.join(root, name)) as f:
                    line = f.readline()
                    while line:
                        if name.endswith(".bib") and "@" in line[:5]:
                            line = f.readline()
                        if prior_id in line:
                            notifications.append(
                                f"Old ID ({prior_id}, to {new_id} in "
                                f"the MAIN_REFERENCES) found in file: {name}"
                            )
                        line = f.readline()
        for name in dirs:
            if any((x in name) or (x in root) for x in ignore_patterns):
                continue
            if prior_id in name:
                notifications.append(
                    f"Old ID ({prior_id}, changed to {new_id} in the "
                    f"MAIN_REFERENCES) found in filepath: {name}"
                )
    return notifications


def check_persisted_ID_changes(prior: dict, data: dict) -> None:
    if "persisted_IDs" not in prior:
        return
    for prior_origin, prior_id in prior["persisted_IDs"]:
        if prior_origin not in [x[0] for x in data["persisted_IDs"]]:
            # Note: this does not catch origins removed before md_processed
            raise OriginError(f"origin removed: {prior_origin}")
        for new_origin, new_id in data["persisted_IDs"]:
            if new_origin == prior_origin:
                if new_id != prior_id:
                    notifications = check_propagated_IDs(prior_id, new_id)
                    notifications.append(
                        f"ID of processed record changed from {prior_id} to {new_id}"
                    )
                    raise PropagatedIDChange(notifications)
    return


def check_sources(REVIEW_MANAGER) -> None:
    SOURCES = REVIEW_MANAGER.paths["SOURCES"]
    SEARCHDIR = REVIEW_MANAGER.paths["SEARCHDIR"]
    search_type_opts = REVIEW_MANAGER.search_type_opts

    if not SOURCES.is_file():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), SOURCES)

    with open(SOURCES) as f:
        sources_df = pd.json_normalize(safe_load(f))
        sources = sources_df.to_dict("records")

    for search_file in SEARCHDIR.glob("*.bib"):
        if str(search_file.name) not in [x["filename"] for x in sources]:
            raise SearchDetailsError(
                "Search file not in sources.yaml " f"({search_file})"
            )

    date_regex = r"^\d{4}-\d{2}-\d{2}$"
    for search_record in sources:
        missing_cols = [
            x
            for x in [
                "filename",
                "search_type",
                "source_name",
                "source_url",
                "search_parameters",
                "comment",
            ]
            if x not in search_record
        ]

        if any(missing_cols):
            raise SearchDetailsError(f"Missing columns in {SOURCES}: {missing_cols}")

        search_record_filename = SEARCHDIR / Path(search_record["filename"])
        if not search_record_filename.is_file():
            logging.warning(f'Search details without file: {search_record["filename"]}')
            # raise SearchDetailsError(f'File not found: {search_record["filename"]}')

        if search_record["search_type"] not in search_type_opts:
            raise SearchDetailsError(
                f'{search_record["search_type"]} not in {search_type_opts}'
            )
        if "completion_date" in search_record:
            if not re.search(date_regex, search_record["completion_date"]):
                raise SearchDetailsError(
                    "completion date not matching YYYY-MM-DD format: "
                    f'{search_record["completion_date"]}'
                )
        if "start_date" in search_record:
            if not re.search(date_regex, search_record["start_date"]):
                raise SearchDetailsError(
                    "start_date date not matchin YYYY-MM-DD format: "
                    f'{search_record["start_date"]}'
                )

    return


def check_raw_search_unchanged(REVIEW_MANAGER) -> None:
    SEARCHDIR = REVIEW_MANAGER.paths["SEARCHDIR"]
    if not SEARCHDIR.is_dir():
        return

    git_repo = git.Repo(str(REVIEW_MANAGER.paths["REPO_DIR"]))

    for commit in list(git_repo.iter_commits()):
        files_in_prev_commit = [k for k, v in commit.stats.files.items()]
        break

    changedFiles = [item.a_path for item in git_repo.index.diff("HEAD")]
    changedFilesWTree = [item.a_path for item in git_repo.index.diff(None)]

    for search_file in SEARCHDIR.glob("**/*"):
        if search_file in files_in_prev_commit and (
            search_file in changedFiles or search_file in changedFilesWTree
        ):
            raise RawSearchChangedError(search_file)
    return


class ReviewManager:

    csl_fallback = (
        "https://raw.githubusercontent.com/citation-style-language/"
        + "styles/6152ccea8b7d7a472910d36524d1bf3557a83bfc/mis-quarterly.csl"
    )

    word_template_url_fallback = (
        "https://raw.githubusercontent.com/geritwagner/templates/main/MISQ.docx"
    )

    search_type_opts = [
        "DB",
        "TOC",
        "BACK_CIT",
        "FORW_CIT",
        "LOCAL_PAPER_INDEX",
        "OTHER",
        "FEED",
    ]

    notified_next_process = None

    def __init__(self, path: str = None) -> None:
        if path is not None:
            self.path = path
        else:
            self.path = os.getcwd()

        self.__git_repo = git.Repo(path)
        self.paths = get_file_paths(self.path)
        self.config = self.__load_config()

        if self.config["DEBUG_MODE"]:
            self.report_logger = setup_report_logger(logging.DEBUG)
            self.logger = setup_logger(logging.DEBUG)
        else:
            self.report_logger = setup_report_logger(logging.INFO)
            self.logger = setup_logger(logging.INFO)

        self.sources = self.load_sources()

        try:
            self.config["DATA_FORMAT"] = ast.literal_eval(self.config["DATA_FORMAT"])
        except ValueError:
            self.logger.error(
                f'Could not load DATA_FORMAT ({self.config["DATA_FORMAT"] }), '
                "using fallback"
            )
            self.config["DATA_FORMAT"] = ["MANUSCRIPT"]
            pass

        self.logger.debug(f"config: {pp.pformat(self.config)}")
        self.logger.debug(f"paths: {pp.pformat(self.paths)}")

    def __load_config(self) -> dict:
        local_config = configparser.ConfigParser()
        confs = []
        if self.paths["SHARED_CONFIG"].is_file():
            confs.append(self.paths["SHARED_CONFIG"])
        if self.paths["PRIVATE_CONFIG"].is_file():
            confs.append(self.paths["PRIVATE_CONFIG"])
        local_config.read(confs)
        config = dict(
            DELAY_AUTOMATED_PROCESSING=local_config.getboolean(
                "general", "DELAY_AUTOMATED_PROCESSING", fallback=True
            ),
            BATCH_SIZE=local_config.getint("general", "BATCH_SIZE", fallback=500),
            SHARE_STAT_REQ=local_config.get(
                "general", "SHARE_STAT_REQ", fallback="PROCESSED"
            ),
            CPUS=local_config.getint("general", "CPUS", fallback=mp.cpu_count() - 1),
            EMAIL=local_config.get("general", "EMAIL", fallback=email_fallback()),
            GIT_ACTOR=local_config.get(
                "general", "GIT_ACTOR", fallback=actor_fallback()
            ),
            DEBUG_MODE=local_config.getboolean("general", "DEBUG_MODE", fallback=False),
            DATA_FORMAT=local_config.get(
                "general", "DATA_FORMAT", fallback='["MANUSCRIPT"]'
            ),
            PDF_HANDLING=local_config.get("general", "PDF_HANDLING", fallback="EXT"),
            ID_PATTERN=local_config.get(
                "general", "ID_PATTERN", fallback="THREE_AUTHORS_YEAR"
            ),
            CSL=local_config.get("general", "CSL", fallback=self.csl_fallback),
            WORD_TEMPLATE_URL=local_config.get(
                "general", "WORD_TEMPLATE_URL", fallback=self.word_template_url_fallback
            ),
        )
        return config

    def check_repo(self) -> dict:
        """Check whether the repository is in a consistent state
        Entrypoint for pre-commit hooks)
        """
        # Note : we have to return status code and message
        # because printing from other packages does not work in pre-commit hook.

        # We work with exceptions because each issue may be raised in different checks.
        self.notified_next_process = ProcessType.check
        PASS, FAIL = 0, 1
        check_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {"script": check_git_installed, "params": []},
            {"script": check_docker_installed, "params": []},
            {"script": check_git_conflicts, "params": self},
            {"script": build_docker_images, "params": self},
            {"script": check_repository_setup, "params": self},
            {"script": check_software, "params": self},
            # {"script": check_raw_search_unchanged, "params": self},
        ]

        if not self.paths["MAIN_REFERENCES"].is_file():
            self.logger.debug("Checks for MAIN_REFERENCES not activated")
        else:
            # Note : retrieving data once is more efficient than
            # reading the MAIN_REFERENCES multiple times (for each check)

            git_repo = self.get_repo()
            if self.paths["MAIN_REFERENCES"] in [
                x.path for x in git_repo.head.commit.tree
            ]:
                prior = retrieve_prior(self)
                self.logger.debug("prior")
                self.logger.debug(pp.pformat(prior))
            else:  # if MAIN_REFERENCES not yet in git history
                prior = {}

            data = retrieve_data(prior, self.paths["MAIN_REFERENCES"])
            self.logger.debug("data")
            self.logger.debug(pp.pformat(data))

            main_refs_checks = [
                {"script": check_persisted_ID_changes, "params": [prior, data]},
                {"script": check_sources, "params": self},
                {"script": check_main_references_duplicates, "params": data},
                {"script": check_main_references_origin, "params": [self, prior, data]},
                {"script": check_main_references_status_fields, "params": data},
                {"script": check_main_references_files, "params": data},
                {"script": check_main_references_status_transitions, "params": data},
                {"script": check_main_references_screen, "params": data},
            ]
            check_scripts += main_refs_checks
            if prior == {}:  # Selected checks if MAIN_REFERENCES not yet in git history
                main_refs_checks = [
                    x
                    for x in main_refs_checks
                    if x["script"]
                    in [
                        "check_sources",
                        "check_main_references_duplicates",
                        "check_main_references_origin",
                        "check_main_references_status_fields",
                        "check_main_references_files",
                    ]
                ]
            self.logger.debug("Checks for MAIN_REFERENCES activated")

            PAPER = self.paths["PAPER"]
            if not PAPER.is_file():
                self.logger.debug("Checks for PAPER not activated\n")
            else:
                manuscript_checks = [
                    {
                        "script": check_new_record_source_tag,
                        "params": PAPER,
                    },
                    {
                        "script": check_update_synthesized_status,
                        "params": [self],
                    },
                ]
                check_scripts += manuscript_checks
                self.logger.debug("Checks for PAPER activated\n")

            # TODO: checks for structured data
            # See functions in comments
            # if DATA.is_file():
            #     data = pd.read_csv(DATA, dtype=str)
            #     check_duplicates_data(data)
            # check_screen_data(screen, data)
            # DATA = REVIEW_MANAGER.paths['DATA']

        try:

            for check_script in check_scripts:
                if [] == check_script["params"]:
                    self.logger.debug(f'{check_script["script"].__name__}() called')
                    check_script["script"]()
                else:
                    # TODO
                    # if type(check_script["params"]) != list:
                    #     param_names = check_script["params"]
                    # else:
                    #     param_names = [x.__name__ for x in check_script["params"]]
                    self.logger.debug(
                        f'{check_script["script"].__name__}(params) called'
                    )
                    if type(check_script["params"]) == list:
                        check_script["script"](*check_script["params"])
                    else:
                        check_script["script"](check_script["params"])
                self.logger.debug(f'{check_script["script"].__name__}: passed\n')

        except (
            MissingDependencyError,
            GitConflictError,
            PropagatedIDChange,
            RawSearchChangedError,
            DuplicatesError,
            OriginError,
            FieldError,
            StatusTransitionError,
            ManuscriptRecordSourceTagError,
            UnstagedGitChangesError,
            StatusFieldValueError,
        ) as e:
            pass
            return {"status": FAIL, "msg": f"{type(e).__name__}: {e}"}
        return {"status": PASS, "msg": "Everything ok."}

    def report(self, msg_file: Path) -> dict:
        """Append commit-message report if not already available
        Entrypoint for pre-commit hooks)
        """
        update = False
        with open(msg_file) as f:
            contents = f.read()
            if "Command" not in contents:
                update = True
            if "Certified properties" in contents:
                update = False
        with open(msg_file, "w") as f:
            f.write(contents)
            # Don't append if it's already there
            if update:
                report = self.__get_commit_report("MANUAL", saved_args=None)
                f.write(report)

        return {"msg": "TODO", "status": 0}

    def sharing(self) -> dict:
        """Check whether sharing requirements are met
        Entrypoint for pre-commit hooks)
        """

        from colrev_core import status

        stat = status.get_status_freq(self)
        collaboration_instructions = status.get_collaboration_instructions(self, stat)
        status_code = all(
            ["SUCCESS" == x["level"] for x in collaboration_instructions["items"]]
        )
        msgs = "\n ".join(
            [
                x["level"] + x["title"] + x.get("msg", "")
                for x in collaboration_instructions["items"]
            ]
        )
        return {"msg": msgs, "status": status_code}

    def __format_main_references(self) -> None:
        from colrev_core import prep

        records = self.load_records()
        for record in records:
            if record["status"] == RecordState.md_needs_manual_preparation:
                prior = record.get("man_prep_hints", "")
                record = prep.log_notifications(record, record.copy())
                record = prep.update_metadata_status(record)
                if record["status"] == RecordState.md_prepared:
                    record["metadata_source"] = "MANUAL"
                if RecordState.md_needs_manual_preparation == record["status"]:
                    if "change-score" in prior:
                        record["man_prep_hints"] += (
                            "; " + prior[prior.find("change-score") :]
                        )
                else:
                    if record.get("man_prep_hints", "NA") == "":
                        del record["man_prep_hints"]

        records = sorted(records, key=lambda d: d["ID"])

        self.save_records(records)
        self.__update_status_yaml()
        return

    def format_references(self) -> dict:
        """Format the references
        Entrypoint for pre-commit hooks)
        """

        from colrev_core.review_manager import ProcessType
        from colrev_core.review_manager import Process

        PASS, FAIL = 0, 1
        MAIN_REFERENCES = self.paths["MAIN_REFERENCES"]
        if not MAIN_REFERENCES.is_file():
            return {"status": PASS, "msg": "Everything ok."}

        try:
            self.notify(Process(ProcessType.format))
            self.__format_main_references()
        except (UnstagedGitChangesError, StatusFieldValueError) as e:
            pass
            return {"status": FAIL, "msg": f"{type(e).__name__}: {e}"}

        if MAIN_REFERENCES in [r.a_path for r in self.__git_repo.index.diff(None)]:
            return {"status": FAIL, "msg": "references formatted"}
        else:
            return {"status": PASS, "msg": "Everything ok."}

    def get_repo(self) -> git.Repo:
        """Get the git repository object (requires REVIEW_MANAGER.notify(...))"""

        if self.notified_next_process is None:
            raise ReviewManagerNotNofiedError()
        return self.__git_repo

    def load_records(self, init: bool = False) -> typing.List[dict]:
        """Get the records (requires REVIEW_MANAGER.notify(...))"""

        if self.notified_next_process is None:
            raise ReviewManagerNotNofiedError()

        from bibtexparser.bparser import BibTexParser
        from bibtexparser.customization import convert_to_unicode

        MAIN_REFERENCES = self.paths["MAIN_REFERENCES"]

        if MAIN_REFERENCES.is_file():
            with open(MAIN_REFERENCES) as target_db:
                bib_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=False,
                    common_strings=True,
                ).parse_file(target_db, partial=True)

                records = bib_db.entries

                # Cast status to Enum
                records = [
                    {k: RecordState[v] if ("status" == k) else v for k, v in r.items()}
                    for r in records
                ]

        else:
            if init:
                records = []
            else:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), MAIN_REFERENCES
                )

        return records

    def save_records(self, records: typing.List[dict]) -> None:
        """Save the records"""

        # Casting to string (in particular the RecordState Enum)
        records = [{k: str(v) for k, v in r.items()} for r in records]

        bib_db = BibDatabase()
        bib_db.entries = records

        bibtex_str = bibtexparser.dumps(bib_db, get_bibtex_writer())

        with open(self.paths["MAIN_REFERENCES"], "w") as out:
            out.write(bibtex_str)

        # Casting to RecordState (in case the records are used afterwards)
        records = [
            {k: RecordState[v] if ("status" == k) else v for k, v in r.items()}
            for r in records
        ]

        return

    def get_record_state_list_from_file_obj(self, file_object) -> list:
        """Get the record_state_list"""

        return [
            get_record_status_item(record_header_str)
            for record_header_str in self.read_next_record_header_str(file_object)
        ]

    def get_record_state_list(self) -> list:
        """Get the record_state_list"""

        if not self.paths["MAIN_REFERENCES"].is_file():
            return []
        return [
            get_record_status_item(record_header_str)
            for record_header_str in self.read_next_record_header_str()
        ]

    def get_record_header_list(self) -> list:
        """Get the record_header_list"""

        if not self.paths["MAIN_REFERENCES"].is_file():
            return []
        return [
            get_record_header_item(record_header_str)
            for record_header_str in self.read_next_record_header_str()
        ]

    def get_states_set(self, record_state_list: list = None) -> set:
        """Get the record_states_set"""

        if not self.paths["MAIN_REFERENCES"].is_file():
            return set()
        if record_state_list is None:
            record_state_list = self.get_record_state_list()
        return {el[1] for el in record_state_list}

    def notify(self, process: Process) -> None:
        """Notify the REVIEW_MANAGER about the next process"""
        self.__check_precondition(process)

    def __check_precondition(self, process: Process) -> None:
        # TODO : currently a special case (not in state model):
        if process.type.name in ["format"]:
            # require_clean_repo_general(ignore_pattern=[self.paths["MAIN_REFERENCES_RELATIVE"]])
            # PDFs etc. can be modified!
            pass
        else:
            # perform a transition in the Record (state model)
            # to call the corresponding condition check
            condition_check_record = Record(
                "checker", Process.get_source_state(process), self
            )
            class_method = getattr(condition_check_record, process.type.name)
            class_method(condition_check_record)

        self.notified_next_process = process.type
        if not self.__git_repo.is_dirty():
            self.__reset_log()

    def run_process(self, process: Process, *args) -> None:
        """Pass a process to the REVIEW_MANAGER for execution"""

        proc_fun = inspect.getmodule(process.processing_function)
        if proc_fun:
            function_name = (
                f"{proc_fun.__name__}." + f"{process.processing_function.__name__}"
            )
        else:
            function_name = "NA"

        self.report_logger.info(
            f"ReviewManager: check_precondition({function_name}, "
            + f"a {process.type.name} process)"
        )
        self.__check_precondition(process)
        self.report_logger.info(f"ReviewManager: run {function_name}()")
        process.run(self, *args)
        self.notified_next_process = None

    def __get_commit_report(
        self, script_name: str = None, saved_args: dict = None
    ) -> str:
        from colrev_core import status

        report = "\n\nReport\n\n"

        git_repo = self.__git_repo

        if script_name is not None:
            if "MANUAL" == script_name:
                report = report + "Commit created manually or by external script\n\n"
            elif " " in script_name:
                script_name = script_name.replace("colrev_core", "colrev").replace(
                    "colrev cli", "colrev"
                )
                script_name = (
                    script_name.split(" ")[0]
                    + " "
                    + script_name.split(" ")[1].replace("_", "-")
                )

                report = report + f"Command\n   {script_name}\n"
        if saved_args is not None:
            for k, v in saved_args.items():
                if (
                    isinstance(v, str)
                    or isinstance(v, bool)
                    or isinstance(v, int)
                    or isinstance(v, float)
                ):
                    if v == "":
                        report = report + f"     --{k}\n"
                    else:
                        report = report + f"     --{k}={v}\n"
            try:
                report = (
                    report
                    + f"   On git repo with version {git_repo.head.commit.hexsha}\n"
                )
            except ValueError:
                pass

        # url = g.execut['git', 'config', '--get remote.origin.url']

        # append status
        f = io.StringIO()
        with redirect_stdout(f):
            stat = status.get_status_freq(self)
            status.print_review_status(self, stat)

        # Remove colors for commit message
        status_page = (
            f.getvalue()
            .replace("\033[91m", "")
            .replace("\033[92m", "")
            .replace("\033[93m", "")
            .replace("\033[94m", "")
            .replace("\033[0m", "")
        )
        status_page = status_page.replace("Status\n\n", "Status\n")
        report = report + status_page

        tree_hash = git_repo.git.execute(["git", "write-tree"])
        if self.paths["MAIN_REFERENCES"].is_file():
            tree_info = f"Certified properties for tree {tree_hash}\n"  # type: ignore
            report = report + "\n\n" + tree_info
            report = report + "   - Traceability of records ".ljust(38, " ") + "YES\n"
            report = (
                report + "   - Consistency (based on hooks) ".ljust(38, " ") + "YES\n"
            )
            completeness_condition = status.get_completeness_condition(self)
            if completeness_condition:
                report = (
                    report + "   - Completeness of iteration ".ljust(38, " ") + "YES\n"
                )
            else:
                report = (
                    report + "   - Completeness of iteration ".ljust(38, " ") + "NO\n"
                )
            report = (
                report
                + "   To check tree_hash use".ljust(38, " ")
                + "git log --pretty=raw -1\n"
            )
            report = (
                report
                + "   To validate use".ljust(38, " ")
                + "colrev_core validate --properties "
                + "--commit INSERT_COMMIT_HASH"
            )
        report = report + "\n"

        report = report + "\nSoftware"
        rt_version = version("colrev_core")
        report = report + "\n   - colrev_core:".ljust(33, " ") + "version " + rt_version
        version("colrev_hooks")
        report = (
            report
            + "\n   - colrev hooks:".ljust(33, " ")
            + "version "
            + version("colrev_hooks")
        )
        sys_v = sys.version
        report = (
            report
            + "\n   - Python:".ljust(33, " ")
            + "version "
            + sys_v[: sys_v.find(" ")]
        )

        stream = os.popen("git --version")
        git_v = stream.read()
        # git_v = git.Git.execute(["git", "--version"])
        report = (
            report
            + "\n   - Git:".ljust(33, " ")
            + git_v.replace("git ", "").replace("\n", "")
        )
        stream = os.popen("docker --version")
        docker_v = stream.read()
        report = (
            report
            + "\n   - Docker:".ljust(33, " ")
            + docker_v.replace("Docker ", "").replace("\n", "")
        )
        if script_name is not None:
            ext_script = script_name.split(" ")[0]
            if ext_script != "colrev_core":
                try:
                    script_version = version(ext_script)
                    report = (
                        report
                        + f"\n   - {ext_script}:".ljust(33, " ")
                        + "version "
                        + script_version
                    )
                except importlib.metadata.PackageNotFoundError:
                    pass

        if "dirty" in report:
            report = (
                report + "\n    * created with a modified version (not reproducible)"
            )
        report = report + "\n"

        return report

    def __get_version_flag(self) -> str:
        flag = ""
        if "dirty" in version("colrev_core"):
            flag = "*"
        return flag

    def __update_status_yaml(self) -> None:
        from colrev_core import status

        status_freq = status.get_status_freq(self)

        with open("status.yaml", "w") as f:
            yaml.dump(status_freq, f, allow_unicode=True)

        git_repo = self.get_repo()
        git_repo.index.add(["status.yaml"])

        return

    def reprocess_id(self, id: str) -> None:
        """Remove an ID (set of IDs) from the bib_db (for reprocessing)"""

        saved_args = locals()

        git_repo = self.get_repo()
        if "all" == id:
            logging.info("Removing/reprocessing all records")
            os.remove(self.paths["MAIN_REFERENCES"])
            git_repo.index.remove(
                [str(self.paths["MAIN_REFERENCES_RELATIVE"])], working_tree=True
            )
        else:
            records = self.load_records()
            records = [x for x in records if id != x["ID"]]
            self.save_records(records)
            git_repo.index.add([str(self.paths["MAIN_REFERENCES_RELATIVE"])])

        self.create_commit("Reprocess", saved_args=saved_args)

        return

    def __reset_log(self) -> None:

        self.report_logger.handlers[0].stream.close()
        self.report_logger.removeHandler(self.report_logger.handlers[0])

        with open("report.log", "r+") as f:
            f.truncate(0)

        file_handler = logging.FileHandler("report.log")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        self.report_logger.addHandler(file_handler)

        return

    def reorder_log(self, IDs: list, criterion=None) -> None:
        """Reorder the report.log according to an ID list (after multiprocessing)"""

        # https://docs.python.org/3/howto/logging-cookbook.html
        # #logging-to-a-single-file-from-multiple-processes

        self.report_logger.handlers[0].stream.close()
        self.report_logger.removeHandler(self.report_logger.handlers[0])

        firsts = []
        ordered_items = ""
        consumed_items = []
        with open("report.log") as r:
            items = []
            item = ""
            for line in r.readlines():
                if any(
                    x in line
                    for x in [
                        "[INFO] Prepare",
                        "[INFO] Completed ",
                        "[INFO] Batch size",
                        "[INFO] Summary: Prepared",
                        "[INFO] Further instructions ",
                        "[INFO] To reset the metdatata",
                        "[INFO] Summary: ",
                        "[INFO] Continuing batch ",
                        "[INFO] Load references.bib",
                        "[INFO] Calculate statistics",
                        "[INFO] ReviewManager: run ",
                        "[INFO] Retrieve PDFs",
                        "[INFO] Statistics:",
                        "[INFO] Set ",
                    ]
                ):
                    firsts.append(line)
                    continue
                if re.search(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ", line):
                    if item != "":
                        item = item.replace("\n\n", "\n").replace("\n\n", "\n")
                        items.append(item)
                        item = ""
                    item = line
                else:
                    item = item + line
            items.append(item.replace("\n\n", "\n").replace("\n\n", "\n"))

        if criterion is None:
            for ID in IDs:
                for item in items:
                    # if f'({ID})' in item:
                    if f"({ID})" in item:
                        formatted_item = item
                        if "] prepare(" in formatted_item:
                            formatted_item = f"\n\n{formatted_item}"
                        ordered_items = ordered_items + formatted_item
                        consumed_items.append(item)

            for x in consumed_items:
                if x in items:
                    items.remove(x)

        if criterion == "descending_thresholds":
            item_details = []
            while items:
                item = items.pop()
                confidence_value = re.search(r"\(confidence: (\d.\d{0,3})\)", item)
                if confidence_value:
                    item_details.append([confidence_value.group(1), item])
                    consumed_items.append(item)
                else:
                    firsts.append(item)

            item_details.sort(key=lambda x: x[0])
            ordered_items = "".join([x[1] for x in item_details])

        formatted_report = (
            "".join(firsts)
            + "\nDetailed report\n"
            + ordered_items.lstrip("\n")
            + "\n\n"
            + "".join(items)
        )
        with open("report.log", "w") as f:
            f.write(formatted_report)

        file_handler = logging.FileHandler("report.log")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        self.report_logger.addHandler(file_handler)

        return

    def create_commit(
        self, msg: str, manual_author: bool = False, saved_args: dict = None
    ) -> bool:
        """Create a commit (including a commit report)"""

        if self.__git_repo.is_dirty():

            self.__update_status_yaml()
            self.__git_repo.index.add(["status.yaml"])

            hook_skipping = False
            if not self.config["DEBUG_MODE"]:
                hook_skipping = True

            processing_report = ""
            if self.paths["REPORT"].is_file():

                # Reformat
                prefixes = [
                    "[('change', 'author',",
                    "[('change', 'title',",
                    "[('change', 'journal',",
                    "[('change', 'booktitle',",
                ]
                temp = tempfile.NamedTemporaryFile()
                self.paths["REPORT"].rename(temp.name)
                with open(temp.name) as reader, open(
                    self.paths["REPORT"], "w"
                ) as writer:
                    line = reader.readline()
                    while line:
                        if (
                            any(prefix in line for prefix in prefixes)
                            and "', '" in line[30:]
                        ):
                            split_pos = line.rfind("', '") + 2
                            indent = line.find("', (") + 3
                            writer.write(line[:split_pos] + "\n")
                            writer.write(" " * indent + line[split_pos:])
                        else:
                            writer.write(line)

                        line = reader.readline()

                with open("report.log") as f:
                    line = f.readline()
                    debug_part = False
                    while line:
                        # For more efficient debugging (loading of dict with Enum)
                        if "'status" == line.lstrip()[:7] and "<RecordState." in line:
                            line = line.replace("<RecordState", "RecordState")
                            line = line[: line.rfind(":")] + line[line.rfind(">") + 1 :]
                        if "[DEBUG]" in line or debug_part:
                            debug_part = True
                            if any(
                                x in line
                                for x in ["[INFO]", "[ERROR]", "[WARNING]", "[CRITICAL"]
                            ):
                                debug_part = False
                        if not debug_part:
                            processing_report = processing_report + line
                        line = f.readline()

                processing_report = "\nProcessing report\n" + "".join(processing_report)

            caller = sys._getframe(1)
            from inspect import stack

            script = (
                str(caller.f_globals["__name__"]).replace("-", "_").replace(".", " ")
                + " "
                + str(stack()[1].function)
            )
            if "Update pre-commit-config" in msg:
                script = "pre-commit autoupdate"

            if manual_author:
                git_author = git.Actor(self.config["GIT_ACTOR"], self.config["EMAIL"])
            else:
                git_author = git.Actor(f"script:{script}", "")

            self.__git_repo.index.commit(
                msg
                + self.__get_version_flag()
                + self.__get_commit_report(f"{script}", saved_args)
                + processing_report,
                author=git_author,
                committer=git.Actor(self.config["GIT_ACTOR"], self.config["EMAIL"]),
                skip_hooks=hook_skipping,
            )
            self.logger.info("Created commit")
            self.__reset_log()
            if self.__git_repo.is_dirty():
                raise DirtyRepoAfterProcessingError
            return True
        else:
            return False

    def set_IDs(
        self, records: typing.List[dict] = [], selected_IDs: list = None
    ) -> typing.List[dict]:
        """Set the IDs of records according to predefined formats"""

        if len(records) == 0:
            records = self.load_records()

        ID_list = [record["ID"] for record in records]

        for record in records:
            if selected_IDs is not None:
                if record["ID"] not in selected_IDs:
                    continue
            elif str(record["status"]) not in [
                str(RecordState.md_imported),
                str(RecordState.md_prepared),
            ]:
                continue

            old_id = record["ID"]
            new_id = self.generate_ID_blacklist(
                record, ID_list, record_in_bib_db=True, raise_error=False
            )
            record.update(ID=new_id)
            ID_list.append(new_id)
            if old_id != new_id:
                self.report_logger.info(f"set_ID({old_id}) to {new_id}")
                if old_id in ID_list:
                    ID_list.remove(old_id)

        records = sorted(records, key=lambda d: d["ID"])

        self.save_records(records)

        # Note : temporary fix
        # (to prevent failing format checks caused by special characters)
        records = self.load_records()
        self.save_records(records)

        git_repo = self.get_repo()
        git_repo.index.add([str(self.paths["MAIN_REFERENCES_RELATIVE"])])

        return records

    def propagated_ID(self, ID: str) -> bool:
        """Check whether an ID has been propagated"""

        propagated = False

        if self.paths["DATA"].is_file():
            # Note: this may be redundant, but just to be sure:
            data = pd.read_csv(self.paths["DATA"], dtype=str)
            if ID in data["ID"].tolist():
                propagated = True

        # TODO: also check data_pages?

        return propagated

    def generate_ID(
        self,
        record: dict,
        records: typing.List[dict] = [],
        record_in_bib_db: bool = False,
        raise_error: bool = True,
    ) -> str:
        """Generate a record ID according to the predefined format"""

        if len(records) == 0:
            ID_blacklist = [record["ID"] for record in records]
        else:
            ID_blacklist = []
        ID = self.generate_ID_blacklist(
            record, ID_blacklist, record_in_bib_db, raise_error
        )
        return ID

    def generate_ID_blacklist(
        self,
        record: dict,
        ID_blacklist: list = None,
        record_in_bib_db: bool = False,
        raise_error: bool = True,
    ) -> str:
        """Generate a blacklist to avoid setting duplicate IDs"""

        from colrev_core import prep

        # Make sure that IDs that have been propagated to the
        # screen or data will not be replaced
        # (this would break the chain of evidence)
        if raise_error:
            if self.propagated_ID(record["ID"]):
                raise CitationKeyPropagationError(
                    "WARNING: do not change IDs that have been "
                    + f'propagated to {self.paths["DATA"]} ({record["ID"]})'
                )

        if "" != record.get("author", record.get("editor", "")):
            authors = prep.format_author_field(
                record.get("author", record.get("editor", "Anonymous"))
            ).split(" and ")
        else:
            authors = ["Anonymous"]

        # Use family names
        for author in authors:
            if "," in author:
                author = author.split(",")[0]
            else:
                author = author.split(" ")[0]

        ID_PATTERN = self.config["ID_PATTERN"]

        assert ID_PATTERN in ["FIRST_AUTHOR_YEAR", "THREE_AUTHORS_YEAR"]
        if "FIRST_AUTHOR_YEAR" == ID_PATTERN:
            temp_ID = f'{author.replace(" ", "")}{str(record.get("year", "NoYear"))}'

        if "THREE_AUTHORS_YEAR" == ID_PATTERN:
            temp_ID = ""
            indices = len(authors)
            if len(authors) > 3:
                indices = 3
            for ind in range(0, indices):
                temp_ID = temp_ID + f'{authors[ind].split(",")[0].replace(" ", "")}'
            if len(authors) > 3:
                temp_ID = temp_ID + "EtAl"
            temp_ID = temp_ID + str(record.get("year", "NoYear"))

        if temp_ID.isupper():
            temp_ID = temp_ID.capitalize()
        # Replace special characters
        # (because IDs may be used as file names)
        temp_ID = remove_accents(temp_ID)
        temp_ID = re.sub(r"\(.*\)", "", temp_ID)
        temp_ID = re.sub("[^0-9a-zA-Z]+", "", temp_ID)

        if ID_blacklist is not None:
            if record_in_bib_db:
                # allow IDs to remain the same.
                other_ids = ID_blacklist
                # Note: only remove it once. It needs to change when there are
                # other records with the same ID
                if record["ID"] in other_ids:
                    other_ids.remove(record["ID"])
            else:
                # ID can remain the same, but it has to change
                # if it is already in bib_db
                other_ids = ID_blacklist

            order = 0
            letters = list(string.ascii_lowercase)
            next_unique_ID = temp_ID
            appends: list = []
            while next_unique_ID in other_ids:
                if len(appends) == 0:
                    order += 1
                    appends = [p for p in itertools.product(letters, repeat=order)]
                next_unique_ID = temp_ID + "".join(list(appends.pop(0)))
            temp_ID = next_unique_ID

        return temp_ID

    def load_sources(self) -> list:
        """Load the source details"""

        if self.paths["SOURCES"].is_file():
            with open(self.paths["SOURCES"]) as f:
                sources_df = pd.json_normalize(safe_load(f))
                sources = sources_df.to_dict("records")
        else:
            self.logger.debug(
                f'Sources file does not exist {self.paths["SOURCES"].name}'
            )
            sources = []
        return sources

    def save_sources(self, sources: list) -> None:
        """Save the source details"""

        sources_df = pd.DataFrame(sources)
        orderedCols = [
            "filename",
            "search_type",
            "source_name",
            "source_url",
            "search_parameters",
            "comment",
        ]
        for x in [x for x in sources_df.columns if x not in orderedCols]:
            orderedCols.append(x)
        sources_df = sources_df.reindex(columns=orderedCols)

        with open(self.paths["SOURCES"], "w") as f:
            yaml.dump(
                json.loads(sources_df.to_json(orient="records")),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
        git_repo = self.get_repo()
        git_repo.index.add([str(self.paths["SOURCES_RELATIVE"])])
        return

    def read_next_record_header_str(
        self, file_object=None, HEADER_LENGTH: int = 9
    ) -> typing.Iterator[str]:
        if file_object is None:
            file_object = open(self.paths["MAIN_REFERENCES"])
        data = ""
        first_entry_processed = False
        header_line_count = 0
        while True:
            line = file_object.readline()
            if not line:
                break
            if line[:1] == "%" or line == "\n":
                continue
            if line[:1] != "@":
                if header_line_count < HEADER_LENGTH:
                    header_line_count = header_line_count + 1
                    data += line
            else:
                if "@comment" not in line:
                    if first_entry_processed:
                        yield data
                        header_line_count = 0
                    else:
                        first_entry_processed = True
                data = line
        if "@comment" not in data:
            yield data

    def read_next_record_str(self, file_object=None) -> typing.Iterator[str]:
        if file_object is None:
            file_object = open(self.paths["MAIN_REFERENCES"])
        data = ""
        first_entry_processed = False
        while True:
            line = file_object.readline()
            if not line:
                break
            if line[:1] == "%" or line == "\n":
                continue
            if line[:1] != "@":
                data += line
            else:
                if first_entry_processed:
                    yield data
                else:
                    first_entry_processed = True
                data = line
        yield data

    def read_next_record(self, conditions: dict = None) -> typing.Iterator[dict]:
        records = []
        with open(self.paths["MAIN_REFERENCES"]) as f:
            for record_string in self.read_next_record_str(f):
                parser = BibTexParser(customization=convert_to_unicode)
                db = bibtexparser.loads(record_string, parser=parser)
                record = db.entries[0]
                record["status"] = RecordState[record["status"]]
                if conditions is not None:
                    for key, value in conditions.items():
                        if str(value) == str(record[key]):
                            records.append(record)
                else:
                    records.append(record)
        yield from records

    def replace_field(self, IDs: list, key: str, val_str: str) -> None:

        val = val_str.encode("utf-8")
        current_ID_str = "NA"
        with open(self.paths["MAIN_REFERENCES"], "r+b") as fd:
            seekpos = fd.tell()
            line = fd.readline()
            while line:
                if b"@" in line[:3]:
                    current_ID = line[line.find(b"{") + 1 : line.rfind(b",")]
                    current_ID_str = current_ID.decode("utf-8")

                replacement = None
                if current_ID_str in IDs:
                    if line.lstrip()[: len(key)].decode("utf-8") == key:
                        replacement = line[: line.find(b"{") + 1] + val + b"},\n"

                if replacement:
                    if len(replacement) == len(line):
                        fd.seek(seekpos)
                        fd.write(replacement)
                        fd.flush()
                        os.fsync(fd)
                    else:
                        remaining = fd.read()
                        fd.seek(seekpos)
                        fd.write(replacement)
                        seekpos = fd.tell()
                        fd.flush()
                        os.fsync(fd)
                        fd.write(remaining)
                        fd.truncate()  # if the replacement is shorter...
                        fd.seek(seekpos)
                        line = fd.readline()
                    IDs.remove(current_ID_str)
                    if 0 == len(IDs):
                        return
                seekpos = fd.tell()
                line = fd.readline()
        return

    def update_record_by_ID(self, new_record: dict, delete: bool = False) -> None:

        ID = new_record["ID"]
        new_record["status"] = str(new_record["status"])
        bib_db = BibDatabase()
        bib_db.entries = [new_record]
        replacement = bibtexparser.dumps(bib_db, get_bibtex_writer())

        current_ID_str = "NA"
        with open(self.paths["MAIN_REFERENCES"], "r+b") as fd:
            seekpos = fd.tell()
            line = fd.readline()
            while line:
                if b"@" in line[:3]:
                    current_ID = line[line.find(b"{") + 1 : line.rfind(b",")]
                    current_ID_str = current_ID.decode("utf-8")

                if current_ID_str == ID:
                    line = fd.readline()
                    while (
                        b"@" not in line[:3] and line
                    ):  # replace: drop the current record
                        line = fd.readline()
                    remaining = line + fd.read()
                    fd.seek(seekpos)
                    if not delete:
                        fd.write(replacement.encode("utf-8"))
                    seekpos = fd.tell()
                    fd.flush()
                    os.fsync(fd)
                    fd.write(remaining)
                    fd.truncate()  # if the replacement is shorter...
                    fd.seek(seekpos)
                    line = fd.readline()
                    return

                seekpos = fd.tell()
                line = fd.readline()
        return

    def save_record_list_by_ID(
        self, record_list: list, append_new: bool = False
    ) -> None:

        if record_list == []:
            return

        # Casting to string (in particular the RecordState Enum)
        record_list = [{k: str(v) for k, v in r.items()} for r in record_list]

        bib_db = BibDatabase()
        bib_db.entries = record_list
        parsed = bibtexparser.dumps(bib_db, get_bibtex_writer())

        record_list = [
            {
                "ID": item[item.find("{") + 1 : item.find(",")],
                "record": "@" + item + "\n",
            }
            for item in parsed.split("\n@")
        ]
        # Correct the first and last items
        record_list[0]["record"] = "@" + record_list[0]["record"][2:]
        record_list[-1]["record"] = record_list[-1]["record"][:-1]

        current_ID_str = "NOTSET"
        if self.paths["MAIN_REFERENCES"].is_file():
            with open(self.paths["MAIN_REFERENCES"], "r+b") as fd:
                seekpos = fd.tell()
                line = fd.readline()
                while line:
                    if b"@" in line[:3]:
                        current_ID = line[line.find(b"{") + 1 : line.rfind(b",")]
                        current_ID_str = current_ID.decode("utf-8")
                    if current_ID_str in [x["ID"] for x in record_list]:
                        replacement = [x["record"] for x in record_list][0]
                        record_list = [
                            x for x in record_list if x["ID"] != current_ID_str
                        ]
                        line = fd.readline()
                        while (
                            b"@" not in line[:3] and line
                        ):  # replace: drop the current record
                            line = fd.readline()
                        remaining = line + fd.read()
                        fd.seek(seekpos)
                        fd.write(replacement.encode("utf-8"))
                        seekpos = fd.tell()
                        fd.flush()
                        os.fsync(fd)
                        fd.write(remaining)
                        fd.truncate()  # if the replacement is shorter...
                        fd.seek(seekpos)

                    seekpos = fd.tell()
                    line = fd.readline()

        if len(record_list) > 0:
            if append_new:
                with open(self.paths["MAIN_REFERENCES"], "a") as m_refs:
                    for replacement in record_list:
                        m_refs.write(replacement["record"])

            else:
                self.report_logger.error(
                    "records not written to file: " f'{[x["ID"] for x in record_list]}'
                )

        git_repo = self.get_repo()
        git_repo.index.add([str(self.paths["MAIN_REFERENCES_RELATIVE"])])
        return


if __name__ == "__main__":
    pass
