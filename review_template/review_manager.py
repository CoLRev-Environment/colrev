#!/usr/bin/env python3
import ast
import configparser
import errno
import inspect
import io
import json
import logging
import multiprocessing as mp
import os
import pkgutil
import pprint
import re
import subprocess
import sys
import unicodedata
from contextlib import redirect_stdout
from enum import auto
from enum import Enum
from importlib.metadata import version
from string import ascii_lowercase

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
from review_template import screen

logging.getLogger("transitions").setLevel(logging.WARNING)

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


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
        wo_ac = [rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)]
        wo_ac = "".join(wo_ac)
    except ValueError:
        wo_ac = input_str
        pass
    return wo_ac


def inplace_change(filename: str, old_string: str, new_string: str) -> None:
    with open(filename) as f:
        s = f.read()
        if old_string not in s:
            logging.info(f'"{old_string}" not found in {filename}.')
            return
    with open(filename, "w") as f:
        s = s.replace(old_string, new_string)
        f.write(s)
    return


def retrieve_package_file(template_file: str, target: str) -> None:
    filedata = pkgutil.get_data(__name__, template_file)
    filedata = filedata.decode("utf-8")
    with open(target, "w") as file:
        file.write(filedata)
    return


def create_state_machine_diagram():
    from transitions.extensions import GraphMachine

    model = Record("test", "pdf_imported")
    machine = GraphMachine(  # noqa F841
        model=model,
        states=Record.states,
        transitions=Record.transitions,
        initial="md_retrieved",
        show_conditions=True,
    )
    model.get_graph().draw("state_machine.png", prog="dot")
    return


class Record:

    # Note : TBD: rev_coded
    states = [
        "md_retrieved",  # without this state, we could not display the load transition
        "md_imported",
        "md_needs_manual_preparation",
        "md_prepared",
        "md_needs_manual_merging",
        "md_processed",
        "rev_retrieved",
        "rev_prescreen_excluded",
        "rev_prescreen_included",
        "pdf_needs_retrieval",
        "pdf_needs_manual_retrieval",
        "pdf_imported",
        "pdf_not_available",
        "pdf_needs_manual_preparation",
        "pdf_prepared",
        "rev_excluded",
        "rev_included",
        "rev_synthesized",
    ]

    transitions = [
        {
            "trigger": "load",
            "source": "md_retrieved",
            "dest": "md_imported",
            "conditions": ["clean_repo_except_search"],
        },
        {
            "trigger": "prepare",
            "source": "md_imported",
            "dest": "md_needs_manual_preparation",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "prepare",
            "source": "md_imported",
            "dest": "md_prepared",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "man_prep",
            "source": "md_needs_manual_preparation",
            "dest": "md_prepared",
            "conditions": [
                "clean_repo_except_main_references",
                "check_records_state_precondition",
            ],
        },
        {
            "trigger": "dedupe",
            "source": "md_prepared",
            "dest": "md_needs_manual_merging",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "dedupe",
            "source": "md_prepared",
            "dest": "md_processed",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "man_dedupe",
            "source": "md_needs_manual_merging",
            "dest": "md_processed",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "automatically",
            "source": "md_processed",
            "dest": "rev_retrieved",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "prescreen",
            "source": "rev_retrieved",
            "dest": "rev_prescreen_excluded",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "prescreen",
            "source": "rev_retrieved",
            "dest": "rev_prescreen_included",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "automatically",
            "source": "rev_prescreen_included",
            "dest": "pdf_needs_retrieval",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "pdf_get",
            "source": "pdf_needs_retrieval",
            "dest": "pdf_imported",
            "conditions": [
                "clean_repo_except_pdf_dir",
                "check_records_state_precondition",
            ],
        },
        {
            "trigger": "pdf_get",
            "source": "pdf_needs_retrieval",
            "dest": "pdf_needs_manual_retrieval",
            "conditions": [
                "clean_repo_except_pdf_dir",
                "check_records_state_precondition",
            ],
        },
        {
            "trigger": "pdf_get_man",
            "source": "pdf_needs_manual_retrieval",
            "dest": "pdf_not_available",
            "conditions": [
                "clean_repo_except_pdf_dir",
                "check_records_state_precondition",
            ],
        },
        {
            "trigger": "pdf_get_man",
            "source": "pdf_needs_manual_retrieval",
            "dest": "pdf_imported",
            "conditions": [
                "clean_repo_except_pdf_dir",
                "check_records_state_precondition",
            ],
        },
        {
            "trigger": "pdf_prep",
            "source": "pdf_imported",
            "dest": "pdf_needs_manual_preparation",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "pdf_prep",
            "source": "pdf_imported",
            "dest": "pdf_prepared",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "pdf_prep_man",
            "source": "pdf_needs_manual_preparation",
            "dest": "pdf_prepared",
            "conditions": [
                "clean_repo_except_pdf_dir",
                "check_records_state_precondition",
            ],
        },
        {
            "trigger": "screen",
            "source": "pdf_prepared",
            "dest": "rev_excluded",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "screen",
            "source": "pdf_prepared",
            "dest": "rev_included",
            "conditions": ["clean_repo", "check_records_state_precondition"],
        },
        {
            "trigger": "data",
            "source": "rev_included",
            "dest": "rev_synthesized",
            "conditions": [
                "clean_repo_except_manuscript",
                "check_records_state_precondition",
            ],
        },
    ]

    def __init__(self, ID, start_state, REVIEW_MANAGER=None):
        print(
            'TODO: what about registering the "planned function call'
            "as an (optional) argument?"
        )
        self.ID = ID
        if REVIEW_MANAGER is not None:
            self.REVIEW_MANAGER = REVIEW_MANAGER

        self.machine = Machine(
            model=self,
            states=Record.states,
            transitions=self.transitions,
            initial=start_state,
        )

    def get_valid_transitions(self):
        return list(
            {x["trigger"] for x in self.transitions if x["source"] == self.state}
        )

    @property
    def check_records_state_precondition(self):
        possible_transitions = [
            x["trigger"] for x in self.transitions if self.state == x["source"]
        ]
        for possible_transition in possible_transitions:
            if self.REVIEW_MANAGER.config["DELAY_AUTOMATED_PROCESSING"]:
                logging.debug(f"precondition: {self.state}")
                process = Process(ProcessType[possible_transition], str)
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
    def clean_repo(self):
        return require_clean_repo_general()

    @property
    def clean_repo_except_search(self):
        return require_clean_repo_general(ignore_pattern="search/")

    @property
    def clean_repo_except_main_references(self):
        MAIN_REFERENCES = "references.bib"  # TODO : this is a temporary fix
        return require_clean_repo_general(ignore_pattern=MAIN_REFERENCES)

    @property
    def clean_repo_except_pdf_dir(self):
        PDF_DIRECTORY = "pdfs/"  # TODO : this is a temporary fix
        return require_clean_repo_general(ignore_pattern=PDF_DIRECTORY)

    @property
    def clean_repo_except_manuscript(self):
        MANUSCRIPT = "paper.md"  # TODO : this is a temporary fix
        return require_clean_repo_general(ignore_pattern=MANUSCRIPT)


class ProcessType(Enum):
    load = auto()
    prepare = auto()
    man_prep = auto()
    dedupe = auto()
    man_dedupe = auto()
    prescreen = auto()
    pdf_get = auto()
    pdf_get_man = auto()
    pdf_prep = auto()
    pdf_prep_man = auto()
    screen = auto()
    data = auto()
    format = auto()
    automatically = auto()

    def __str__(self):
        return f"{self.name}"


class Process:
    def __init__(
        self,
        type: ProcessType,
        fun,
        interactive: bool = None,
    ):
        self.type = type
        if interactive is not None:
            self.interactive = interactive
        else:
            self.interactive = False
        self.processing_function = fun

    def get_source_state(process):
        source_state = [
            x["source"] for x in Record.transitions if x["trigger"] == process.type.name
        ]
        return source_state[0]

    def get_preceding_states(self, state):
        preceding_states = set()
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

    r_header_lines = r_header.split("\n")
    ID = r_header_lines[0]
    ID = ID[ID.find("{") + 1 : ID.rfind(",")]

    status = "NA"
    if "rev_status" not in r_header_lines[2]:
        raise StatusFieldValueError(r_header_lines[0], "rev_status", "NA")

    rev_status = r_header_lines[2]
    rev_status = rev_status[rev_status.find("{") + 1 : rev_status.rfind("}")]
    if "md_status" not in r_header_lines[3]:
        raise StatusFieldValueError(r_header_lines[0], "md_status", "NA")

    md_status = r_header_lines[3]
    md_status = md_status[md_status.find("{") + 1 : md_status.rfind("}")]

    if "retrieved" == rev_status:
        if "retrieved" == md_status:
            status = "md_retrieved"
        elif "imported" == md_status:
            status = "md_imported"
        elif "needs_manual_preparation" == md_status:
            status = "md_needs_manual_preparation"
        elif "prepared" == md_status:
            status = "md_prepared"
        elif "needs_manual_merging" == md_status:
            status = "md_needs_manual_merging"
        elif "processed" == md_status:
            status = "md_processed"
        else:
            raise StatusFieldValueError(r_header_lines[0], "md_status", md_status)

    elif "prescreen_excluded" == rev_status:
        status = "rev_prescreen_excluded"

    elif "prescreen_included" == rev_status:

        status = "rev_prescreen_included"

        # if "pdf_status" not in r_header_lines[4]:
        #     raise StatusFieldValueError(r_header_lines[0], "pdf_status", "NA")

        pdf_status = r_header_lines[4]
        pdf_status = pdf_status[pdf_status.find("{") + 1 : pdf_status.rfind("}")]

        if "needs_retrieval" == pdf_status:
            status = "pdf_needs_retrieval"
        if "needs_manual_retrieval" == pdf_status:
            status = "pdf_needs_manual_retrieval"
        elif "imported" == pdf_status:
            status = "pdf_imported"
        elif "needs_manual_preparation" == pdf_status:
            status = "pdf_needs_manual_preparation"
        elif "prepared" == pdf_status:
            status = "pdf_prepared"
    elif "excluded" == rev_status:
        status = "rev_excluded"
    elif "included" == rev_status:
        status = "rev_included"
    elif "synthesized" == rev_status:
        status = "rev_synthesized"
    else:
        raise StatusFieldValueError(r_header_lines[0], "rev_status", rev_status)

    return [ID, status]


def get_name_mail_from_global_git_config() -> list:
    ggit_conf_path = os.path.normpath(os.path.expanduser("~/.gitconfig"))
    global_conf_details = []
    if os.path.exists(ggit_conf_path):
        glob_git_conf = git.GitConfigParser([ggit_conf_path], read_only=True)
        global_conf_details = [
            glob_git_conf.get("user", "name"),
            glob_git_conf.get("user", "email"),
        ]
    return global_conf_details


def get_bibtex_writer():

    writer = BibTexWriter()

    writer.contents = ["entries", "comments"]
    # Note: IDs should be at the beginning to facilitate git versioning
    writer.display_order = [
        "origin",  # must be in second line
        "rev_status",  # must be in third line
        "md_status",  # must be in fourthline
        "pdf_status",  # must be in fifth line (if available)
        "excl_criteria",
        "man_prep_hints",
        "metadata_source",
        "pdf_processed",
        "file",  # Note : do not change this order (parsers rely on it)
        "doi",
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


def email_fallback() -> str:
    name, email = get_name_mail_from_global_git_config()
    return email


def actor_fallback() -> str:
    name, email = get_name_mail_from_global_git_config()
    return name


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("report.log", mode="a"),
        logging.StreamHandler(),
    ],
)


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


class StatusFieldValueError(Exception):
    def __init__(self, record: str, status_type: str, status_value: str):
        self.message = f"{status_type} set to {status_value} in {record}."
        super().__init__(self.message)


class ProcessOrderViolation(Exception):
    def __init__(self, process: Process, required_states: set, violating_records: list):
        # self.search_results_path = search_results_path
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


def require_clean_repo_general(
    git_repo: git.Repo = None, ignore_pattern: str = None
) -> bool:

    # TODO: we may want to be more specific,
    # i.e.,allow staged/unstaged changes (e.g., in readme.md, ...)
    # TBD : require changes in .pre-commit-config.yaml to be in a separate commit?

    if git_repo is None:
        git_repo = git.Repo()

    # Note : not considering untracked files.

    # Principle: working tree always has to be clean
    # because processing functions may change content
    if git_repo.is_dirty(index=False):
        changedFiles = [item.a_path for item in git_repo.index.diff(None)]
        raise UnstagedGitChangesError(changedFiles)

    if git_repo.is_dirty():
        if ignore_pattern is None:
            changedFiles = [item.a_path for item in git_repo.index.diff(None)] + [
                x.a_path for x in git_repo.head.commit.diff()
            ]
            if "status.yaml" in changedFiles:
                changedFiles.remove("status.yaml")

            raise CleanRepoRequiredError(changedFiles, ignore_pattern)
        else:
            changedFiles = [
                item.a_path
                for item in git_repo.index.diff(None)
                if ignore_pattern not in item.a_path
            ] + [
                x.a_path
                for x in git_repo.head.commit.diff()
                if ignore_pattern not in x.a_path
            ]
            if "status.yaml" in changedFiles:
                changedFiles.remove("status.yaml")
            if changedFiles:
                raise CleanRepoRequiredError(changedFiles, ignore_pattern)
    return True


# Note: dicts are unordered.
# To improve readability, we can put the transition at the beginning.
valid_transitions = [
    {"metadata": "-", "review": "-", "pdf": "-"},
    {"metadata": "NA>non_imported", "review": "NA>retrieved", "pdf": "-"},
    # For local_paper_index: PDFs can be available from the start:
    {"metadata": "NA>non_imported", "review": "NA>retrieved", "pdf": "NA>imported"},
    {"metadata": "non_imported>imported", "review": "-", "pdf": "-"},
    # For prepare --reset-ID:
    {"metadata": "prepared>needs_manual_preparation", "review": "-", "pdf": "-"},
    {"metadata": "imported>prepared", "review": "-", "pdf": "-"},
    {"metadata": "imported>needs_manual_preparation", "review": "-", "pdf": "-"},
    {"metadata": "needs_manual_preparation>prepared", "review": "-", "pdf": "-"},
    {"metadata": "prepared>needs_manual_merging", "review": "-", "pdf": "-"},
    {"metadata": "needs_manual_merging>processed", "review": "-", "pdf": "-"},
    {"metadata": "prepared>processed", "review": "-", "pdf": "-"},
    {"review": "retrieved>prescreen_excluded", "metadata": "-", "pdf": "-"},
    {"review": "retrieved>prescreen_included", "metadata": "-", "pdf": "-"},
    {"pdf": "NA>needs_retrieval", "metadata": "-", "review": "-"},
    {"pdf": "needs_retrieval>needs_manual_retrieval", "metadata": "-", "review": "-"},
    {"pdf": "needs_manual_retrieval>imported", "metadata": "-", "review": "-"},
    {"pdf": "needs_retrieval>imported", "metadata": "-", "review": "-"},
    {"pdf": "imported>needs_manual_preparation", "metadata": "-", "review": "-"},
    {"pdf": "needs_manual_preparation>prepared", "metadata": "-", "review": "-"},
    {"pdf": "imported>prepared", "metadata": "-", "review": "-"},
    {"review": "prescreen_included>excluded", "metadata": "-", "pdf": "-"},
    {"review": "prescreen_included>included", "metadata": "-", "pdf": "-"},
    {"review": "included>synthesized", "metadata": "-", "pdf": "-"},
    {"review": "prescreen_included>coded", "metadata": "-", "pdf": "-"},
    {"review": "coded>synthesized", "metadata": "-", "pdf": "-"},
]


class ConsistencyError(Exception):
    pass


def retrieve_IDs_from_bib(file_path: str) -> list:
    assert file_path.endswith(".bib")
    IDs = []
    with open(file_path) as f:
        line = f.readline()
        while line:
            if "@" in line[:5]:
                ID = line[line.find("{") + 1 : line.rfind(",")]
                IDs.append(ID)
            line = f.readline()
    return IDs


def get_bib_files() -> list:
    search_dir = os.path.join(os.getcwd(), "search/")
    return [
        os.path.join(search_dir, x)
        for x in os.listdir(search_dir)
        if x.endswith(".bib")
    ]


def read_next_record(file_object) -> str:
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


def retrieve_prior(MAIN_REFERENCES: str) -> dict:
    repo = git.Repo()
    revlist = (
        (commit.hexsha, (commit.tree / MAIN_REFERENCES).data_stream.read())
        for commit in repo.iter_commits(paths=MAIN_REFERENCES)
    )
    prior = {"rev_status": [], "md_status": [], "pdf_status": [], "persisted_IDs": []}
    filecontents = list(revlist)[0][1]
    for record_string in read_next_record(io.StringIO(filecontents.decode("utf-8"))):

        ID, rev_stat, md_stat, pdf_stat, origin = "NA", "NA", "NA", "NA", "NA"
        for line in record_string.split("\n"):
            if "@" in line[:3]:
                ID = line[line.find("{") + 1 : line.rfind(",")]
            if "rev_status" == line.lstrip()[:10]:
                rev_stat = line[line.find("{") + 1 : line.rfind("}")]
            if "md_status" == line.lstrip()[:9]:
                md_stat = line[line.find("{") + 1 : line.rfind("}")]
            if "pdf_status" == line.lstrip()[:10]:
                pdf_stat = line[line.find("{") + 1 : line.rfind("}")]
            if "origin" == line.strip()[:6]:
                origin = line[line.find("{") + 1 : line.rfind("}")]
        if "NA" != ID:
            for orig in origin.split(";"):
                prior["rev_status"].append([orig, rev_stat])
                prior["md_status"].append([orig, md_stat])
                prior["pdf_status"].append([orig, pdf_stat])
                if "processed" == md_stat:
                    prior["persisted_IDs"].append([orig, ID])

        else:
            logging.error(f"record without ID: {record_string}")
    return prior


def retrieve_data(prior: dict, MAIN_REFERENCES: str) -> dict:

    data = {
        "missing_pdf_status": [],
        "missing_file": [],
        "pdf_not_exists": [],
        "metadata_status_fields": [],
        "review_status_fields": [],
        "pdf_status_fields": [],
        "status_transitions": [],
        "start_states": [],
        "exclusion_criteria_list": [],
        "IDs": [],
        "entries_without_origin": [],
        "record_links_in_bib": [],
        "status_inconsistencies": [],
        "persisted_IDs": [],
        "origin_list": [],
    }

    with open(MAIN_REFERENCES) as f:
        for record_string in read_next_record(f):
            ID, file, rev_status, md_status, pdf_status, excl_crit, origin = (
                "NA",
                "NA",
                "NA",
                "NA",
                "NA",
                "not_set",
                "NA",
            )
            for line in record_string.split("\n"):
                if "@" in line[:3]:
                    ID = line[line.find("{") + 1 : line.rfind(",")]
                if "file" == line.lstrip()[:4]:
                    file = line[line.find("{") + 1 : line.rfind("}")]
                if "rev_status" == line.lstrip()[:10]:
                    rev_status = line[line.find("{") + 1 : line.rfind("}")]
                if "md_status" == line.lstrip()[:9]:
                    md_status = line[line.find("{") + 1 : line.rfind("}")]
                if "pdf_status" == line.lstrip()[:10]:
                    pdf_status = line[line.find("{") + 1 : line.rfind("}")]
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

            if "processed" == md_status:
                for origin_part in origin.split(";"):
                    data["persisted_IDs"].append([origin_part, ID])

            if file != "NA":
                if not os.path.exists(file):
                    data["pdf_not_exists"].append(ID)

            if origin != "NA":
                for org in origin.split(";"):
                    data["record_links_in_bib"].append(org)
            else:
                data["entries_without_origin"].append(ID)

            state_tuple = [ID, rev_status, md_status, pdf_status]
            if md_status != "processed" and rev_status != "retrieved":
                data["status_inconsistencies"].append(state_tuple)
            if pdf_status != "prepared" and rev_status in [
                "included",
                "excluded",
                "coded",
                "synthesized",
            ]:
                data["status_inconsistencies"].append(state_tuple)

            data["review_status_fields"].append(rev_status)
            data["metadata_status_fields"].append(md_status)
            data["pdf_status_fields"].append(pdf_status)

            if (" file  " in record_string) and (" pdf_status " not in record_string):
                data["missing_pdf_status"].append(ID)
            if (
                (" file  " not in record_string)
                and (" pdf_status " in record_string)
                and not (
                    "{needs_retrieval}" in record_string
                    or "{needs_manual_retrieval}" in record_string
                )
            ):
                data["missing_file"].append(ID)

            if "not_set" != excl_crit:
                ec_case = [ID, rev_status, excl_crit]
                data["exclusion_criteria_list"].append(ec_case)

            prior_rev_status = [
                stat for (org, stat) in prior["rev_status"] if org in origin.split(";")
            ]
            # TODO: the origins of an record could be in multiple md_status
            prior_md_status = [
                stat for (org, stat) in prior["md_status"] if org in origin.split(";")
            ]
            prior_pdf_status = [
                stat for (org, stat) in prior["pdf_status"] if org in origin.split(";")
            ]

            status_transition = {}
            status_transition[ID] = {}
            st = status_transition[ID]
            st["review"] = format_transition(prior_rev_status[0], rev_status)
            st["metadata"] = format_transition(prior_md_status[0], md_status)
            st["pdf"] = format_transition(prior_pdf_status[0], pdf_status)

            if not (st["metadata"] == "-" and st["review"] == "-" and st["pdf"] == "-"):
                start_state = (
                    f"{ID}:{prior_md_status[0]}/"
                    + f"{prior_rev_status[0]}/{prior_pdf_status[0]}"
                )
                data["start_states"].append(start_state)

            data["status_transitions"].append(status_transition)

    return data


class DuplicatesError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


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


class OriginError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


def check_main_references_origin(data: dict) -> None:
    # Check whether each record has an origin
    if not len(data["entries_without_origin"]) == 0:
        raise OriginError(
            f"Entries without origin: {', '.join(data['entries_without_origin'])}"
        )

    # Check for broken origins
    all_record_links = []
    for bib_file in get_bib_files():
        search_IDs = retrieve_IDs_from_bib(bib_file)
        bib_file = os.path.basename(bib_file)
        [all_record_links.append(bib_file + "/" + x) for x in search_IDs]
    delta = set(data["record_links_in_bib"]) - set(all_record_links)
    if len(delta) > 0:
        raise OriginError(f"Broken origins: {delta}")

    # Check for non-unique origins
    origins = [x[1] for x in data["origin_list"]]
    non_unique_origins = []
    for org in origins:
        if origins.count(org) > 1:
            non_unique_origins.append(org)
    if non_unique_origins:
        for ID, org in data["origin_list"]:
            if org in non_unique_origins:
                raise OriginError(
                    f'Non-unique origin: origin="{org}" in record with ID={ID}'
                )
    return


class FieldError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


def check_main_references_status_fields(data: dict) -> None:

    # Check status fields
    md_stat_schema = [
        "non_imported",
        "imported",
        "needs_manual_preparation",
        "prepared",
        "needs_manual_merging",
        "processed",
    ]
    md_stat_diff = set(data["metadata_status_fields"]).difference(md_stat_schema)
    if md_stat_diff:
        raise FieldError(f"md_status field(s) {md_stat_diff} not in {md_stat_schema}")

    rev_stat_schema = [
        "retrieved",
        "prescreen_excluded",
        "prescreen_included",
        "excluded",
        "included",
        "coded",
        "synthesized",
    ]
    rev_stat_diff = set(data["review_status_fields"]).difference(rev_stat_schema)
    if rev_stat_diff:
        raise FieldError(
            f"rev_status field(s) {rev_stat_diff} not in {rev_stat_schema}"
        )

    pdf_stat_schema = [
        "NA",
        "needs_retrieval",
        "needs_manual_retrieval",
        "imported",
        "not_available",
        "needs_manual_preparation",
        "prepared",
    ]
    pdf_stat_diff = set(data["pdf_status_fields"]).difference(pdf_stat_schema)
    if pdf_stat_diff:
        raise FieldError(
            f"pdf_status field(s) {pdf_stat_diff} not in {pdf_stat_schema}"
        )

    if data["status_inconsistencies"]:
        for status_inconsistency in data["status_inconsistencies"]:
            raise FieldError(f"Inconsistent status fields: {status_inconsistency}")

    return


class StatusTransitionError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


def check_main_references_status_transitions(data: dict) -> None:

    # Check transitions
    for status_transition in data["status_transitions"]:
        for id, transition in status_transition.items():
            if transition not in valid_transitions:
                raise StatusTransitionError(
                    f"Invalid state transition for {id}: {transition}"
                )

    start_states = [x.split(":")[1] for x in data["start_states"]]
    if len(set(start_states)) > 1:
        raise StatusTransitionError(
            "Problem: multiple transitions from different "
            f'start states ({set(data["start_states"])})'
        )
    return


def check_main_references_screen(data: dict) -> None:

    # Check screen
    # Note: consistency of inclusion_2=yes -> inclusion_1=yes
    # is implicitly ensured through rev_status
    # (screen2-included/excluded implies prescreen included!)

    if data["exclusion_criteria_list"]:
        exclusion_criteria = data["exclusion_criteria_list"][0][2]
        if exclusion_criteria != "NA":
            criteria = screen.get_exclusion_criteria_from_str(exclusion_criteria)
            pattern = "=(yes|no);".join(criteria) + "=(yes|no)"
            pattern_inclusion = "=no;".join(criteria) + "=no"
        else:
            criteria = "NA"
            pattern = "^NA$"
            pattern_inclusion = "^NA$"
        for [ID, rev_status, excl_crit] in data["exclusion_criteria_list"]:
            # print([ID, rev_status, excl_crit])
            if not re.match(pattern, excl_crit):
                # Note: this should also catch cases of missing
                # exclusion criteria
                raise FieldError(
                    "Exclusion criteria field not matching "
                    f"pattern: {excl_crit} ({ID}; criteria: {criteria})"
                )

            elif "excluded" == rev_status:
                if "NA" == criteria:
                    if "NA" == excl_crit:
                        continue
                    else:
                        raise FieldError(f"excl_crit field not NA: {excl_crit}")

                if "=yes" not in excl_crit:
                    logging.error(f"criteria: {criteria}")
                    raise FieldError(
                        "Excluded record with no exclusion_criterion violated: "
                        f"{ID}, {rev_status}, {excl_crit}"
                    )

            # Note: we don't have to consider the cases of
            # rev_status=retrieved/prescreen_included/prescreen_excluded
            # because they would not have exclusion_criteria.
            else:
                if not re.match(pattern_inclusion, excl_crit):
                    raise FieldError(
                        "Included record with exclusion_criterion satisfied: "
                        f"{ID}, {rev_status}, {excl_crit}"
                    )
    return


def check_main_references_files(data: dict, MAIN_REFERENCES: str) -> None:

    # Check pdf files
    if len(data["missing_pdf_status"]) > 0:
        logging.error(f'Entries with missing pdf_status: {data["missing_pdf_status"]}')
        temp = MAIN_REFERENCES.replace(".bib", "_temp.bib")
        os.rename(MAIN_REFERENCES, temp)
        with open(temp) as f, open(MAIN_REFERENCES, "w") as m:
            for record_string in read_next_record(f):
                for line in record_string.split("\n"):
                    if " file  " in line:
                        line = line + "\n  pdf_status = {imported},\n"
                    m.write(line)
        os.remove(temp)
        raise FieldError(
            "Added pdf_status information. Use git add and commit changes."
        )

    if len(data["missing_file"]) > 0:
        raise FieldError(
            f'Entries with pdf_status but missing file: {data["missing_file"]}'
        )

    if len(data["pdf_not_exists"]) > 0:
        raise FieldError(f'Entries with broken file link: {data["pdf_not_exists"]}')

    return


class RecordSourceTagError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


def check_new_record_source_tag(MANUSCRIPT: str) -> None:

    tag_found = False
    with open(MANUSCRIPT) as f:
        for line in f:
            if "<!-- NEW_RECORD_SOURCE -->" in line:
                tag_found = True
    if not tag_found:
        raise RecordSourceTagError(
            "Did not find <!-- NEW_RECORD_SOURCE --> tag in {MANUSCRIPT}"
        )

    return


# def check_screen_data(screen, data):
#     # Check consistency: data -> inclusion_2

#     global STATUS
#     data_IDs = data['ID'].tolist()
#     screen_IDs = \
#         screen['ID'][screen['inclusion_2'] == 'yes'].tolist()

#     violations = [ID for ID in set(
#         data_IDs) if ID not in set(screen_IDs)]
#     if len(violations) != 0:
#         print('IDs in DATA not coded as inclusion_2=yes: ' +
#               f'{violations}')
#         STATUS = FAIL

#     return


# def check_duplicates_data(data):
#     # Check whether there are duplicate IDs in data.csv

#     global STATUS
#     if not data['ID'].is_unique:
#         print(data[data.duplicated(['ID'])].ID.tolist())
#         STATUS = FAIL

#     return


# def check_id_integrity_data(data, IDs):
#     # Check consistency: all IDs in data.csv in references.bib

#     global STATUS
#     missing_IDs = [ID for
#                              ID in data['ID'].tolist()
#                              if ID not in IDs]
#     if not len(missing_IDs) == 0:
#         print('IDs in data.csv not in MAIN_REFERENCES: ' +
#               str(set(missing_IDs)))
#         STATUS = FAIL
#     return


def check_propagated_IDs(prior_id: str, new_id: str) -> None:

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
                retrieved_IDs = retrieve_IDs_from_bib(os.path.join(root, name))
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


class PropagatedIDChange(Exception):
    def __init__(self, notifications):
        self.message = "\n".join(notifications)
        super().__init__(self.message)


def check_persisted_ID_changes(prior: dict, data: dict) -> None:
    for prior_origin, prior_id in prior["persisted_IDs"]:
        # TBD: notify if the origin no longer exists?
        for new_origin, new_id in data["persisted_IDs"]:
            if new_origin == prior_origin:
                if new_id != prior_id:
                    notifications = check_propagated_IDs(prior_id, new_id)
                    notifications.append(
                        f"ID of processed record changed from {prior_id} to {new_id}"
                    )
                    raise PropagatedIDChange(notifications)
    return


def check_origin_removed(prior: dict, data: dict) -> None:
    # TODO !!!!
    # Raise an exception if origins were removed
    # prior_origins = [x[0] for x in prior['md_status']]
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


class SearchDetailsMissingError(Exception):
    def __init__(
        self,
        search_results_path,
    ):
        self.search_results_path = search_results_path
        self.message = (
            "Search results path "
            + f"({os.path.basename(self.search_results_path)}) "
            + "is not in search_details.yaml"
        )
        super().__init__(self.message)


class SearchDetailsError(Exception):
    def __init__(
        self,
        msg,
    ):
        self.message = f" {msg}"
        super().__init__(self.message)


def check_search_details(SEARCH_DETAILS: str, search_type_opts: list) -> None:
    if not os.path.exists(SEARCH_DETAILS):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), SEARCH_DETAILS)

    with open(SEARCH_DETAILS) as f:
        search_details_df = pd.json_normalize(safe_load(f))
        search_details = search_details_df.to_dict("records")

    search_files = os.listdir("search")

    date_regex = r"^\d{4}-\d{2}-\d{2}$"
    for search_record in search_details:
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
        if search_record["filename"] in search_files:
            search_files.remove(search_record["filename"])
        else:
            raise SearchDetailsError(
                "Search file not in search_details.yaml "
                f'({search_record["filename"]})'
            )

        if any(missing_cols):
            raise SearchDetailsError(
                f"Missing columns in {SEARCH_DETAILS}: {missing_cols}"
            )

        if not os.path.exists(os.path.join("search", search_record["filename"])):
            raise SearchDetailsError(f'File not found: {search_record["filename"]}')

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

    repo = git.Repo("")
    untracked_files = repo.untracked_files
    if search_files:
        for search_file in search_files:
            if os.path.join("search", search_file) not in untracked_files:
                raise SearchDetailsError(
                    f"missing record in {SEARCH_DETAILS} for {search_files}"
                )
    return


class RawSearchChangedError(Exception):
    def __init__(self, path):
        self.message = f"revert changes to raw search results: {path}"
        super().__init__(self.message)


def check_raw_search_unchanged() -> None:
    search_files = [os.path.join("search", x) for x in os.listdir("search")]
    repo = git.Repo()
    revlist = (commit.tree for commit in repo.iter_commits())
    last_tree = list(revlist)[0]
    files_in_prev_commit = [el.path for el in list(last_tree.traverse())]

    changedFiles = [item.a_path for item in repo.index.diff("HEAD")]
    changedFilesWTree = [item.a_path for item in repo.index.diff(None)]

    for search_file in search_files:
        if search_file in files_in_prev_commit and (
            search_file in changedFiles or search_file in changedFilesWTree
        ):
            raise RawSearchChangedError(search_file)
    return


class MissingDependencyError(Exception):
    def __init__(self, dep):
        self.message = f"please install {dep}"
        super().__init__(self.message)


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


class GitConflictError(Exception):
    def __init__(self, path):
        self.message = f"please resolve git conflict in {path}"
        super().__init__(self.message)


def check_git_conflicts() -> None:
    # Note: when check is called directly from the command line.
    # pre-commit hooks automatically notify on merge conflicts

    repo = git.Repo()
    unmerged_blobs = repo.index.unmerged_blobs()

    for path in unmerged_blobs:
        list_of_blobs = unmerged_blobs[path]
        for (stage, blob) in list_of_blobs:
            if stage != 0:
                raise GitConflictError(path)
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
    ]

    notified_next_process = None

    def __init__(self, path: str = None, debug_mode: bool = False):
        if path is not None:
            self.path = path
        else:
            self.path = os.getcwd()

        self.__git_repo = git.Repo()
        self.config = self.load_config()
        self.paths = dict(
            MAIN_REFERENCES="references.bib",
            DATA="data.yaml",
            PDF_DIRECTORY="pdfs/",
            SEARCH_DETAILS="search_details.yaml",
            MANUSCRIPT="paper.md",
        )
        self.search_details = self.load_search_details()

        if debug_mode is not None:
            self.config["DEBUG_MODE"] = debug_mode

        self.logger = logging.getLogger("review_manager")
        if self.config["DEBUG_MODE"]:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

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

    def load_config(self):
        local_config = configparser.ConfigParser()
        confs = []
        if os.path.exists("shared_config.ini"):
            confs.append("shared_config.ini")
        if os.path.exists("private_config.ini"):
            confs.append("private_config.ini")
        local_config.read(confs)
        config = dict(
            REPO_SETUP_VERSION=local_config.get(
                "general", "REPO_SETUP_VERSION", fallback="v_0.1"
            ),
            DELAY_AUTOMATED_PROCESSING=local_config.getboolean(
                "general", "DELAY_AUTOMATED_PROCESSING", fallback=True
            ),
            BATCH_SIZE=local_config.getint("general", "BATCH_SIZE", fallback=500),
            SHARE_STAT_REQ=local_config.get(
                "general", "SHARE_STAT_REQ", fallback="PROCESSED"
            ),
            CPUS=local_config.getint("general", "CPUS", fallback=mp.cpu_count() - 1),
            MERGING_NON_DUP_THRESHOLD=local_config.getfloat(
                "general", "MERGING_NON_DUP_THRESHOLD", fallback=0.75
            ),
            MERGING_DUP_THRESHOLD=local_config.getfloat(
                "general", "MERGING_DUP_THRESHOLD", fallback=0.95
            ),
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
                "general", "ID_PATTERN", fallback="THREE_AUTHORS"
            ),
            CSL=local_config.get("general", "CSL", fallback=self.csl_fallback),
            WORD_TEMPLATE_URL=local_config.get(
                "general", "WORD_TEMPLATE_URL", fallback=self.word_template_url_fallback
            ),
        )
        return config

    def format_main_references(self):
        bib_db = self.load_main_refs()
        self.update_status_yaml()
        self.save_bib_file(bib_db)
        return

    def format_references(self):

        from review_template.review_manager import ProcessType
        from review_template.review_manager import Process

        MAIN_REFERENCES = self.paths["MAIN_REFERENCES"]
        if not os.path.exists(MAIN_REFERENCES):
            return False

        format = Process(ProcessType.format, self.format_main_references)
        self.notify(format)
        self.format_main_references()

        if MAIN_REFERENCES in [
            entry.a_path for entry in self.__git_repo.index.diff(None)
        ]:
            return True
        else:
            return False

    def check_repo(self):
        # Note : we have to return status code and message
        # because printing from other packages does not work in pre-commit hook.

        # We work with exceptions because each issue may be raised in different checks.

        PASS, FAIL = 0, 1

        try:
            check_git_installed()
            check_docker_installed()
            check_git_conflicts()

            check_raw_search_unchanged()
            if os.path.exists(self.paths["MAIN_REFERENCES"]):
                prior = retrieve_prior(self.paths["MAIN_REFERENCES"])
                data = retrieve_data(prior, self.paths["MAIN_REFERENCES"])
                check_persisted_ID_changes(prior, data)
                check_origin_removed(prior, data)

                check_search_details(
                    self.paths["SEARCH_DETAILS"], self.search_type_opts
                )
                check_main_references_duplicates(data)
                check_main_references_origin(data)
                check_main_references_status_fields(data)
                check_main_references_status_transitions(data)
                check_main_references_screen(data)
                check_main_references_files(data, self.paths["MAIN_REFERENCES"])

                MANUSCRIPT = self.paths["MANUSCRIPT"]
                if os.path.exists(MANUSCRIPT):
                    check_new_record_source_tag(MANUSCRIPT)

                # TODO: checks for structured data
                # See functions in comments
                # if os.path.exists(DATA):
                #     data = pd.read_csv(DATA, dtype=str)
                #     check_duplicates_data(data)
                # check_screen_data(screen, data)
                # DATA = repo_setup.paths['DATA']
        except (
            MissingDependencyError,
            GitConflictError,
            PropagatedIDChange,
            RawSearchChangedError,
            DuplicatesError,
            OriginError,
            FieldError,
            StatusTransitionError,
            RecordSourceTagError,
        ) as e:
            pass
            return {"status": FAIL, "msg": f"{type(e).__name__}: {e}"}
        return {"status": PASS, "msg": "Everything ok."}

    def notify(self, process: Process):
        self.check_precondition(process)

    def get_repo(self):
        if self.notified_next_process is None:
            raise ReviewManagerNotNofiedError()
        return self.__git_repo

    def load_main_refs(self, init: bool = None) -> BibDatabase:

        if self.notified_next_process is None:
            raise ReviewManagerNotNofiedError()

        from bibtexparser.bibdatabase import BibDatabase
        from bibtexparser.bparser import BibTexParser
        from bibtexparser.customization import convert_to_unicode

        if init is None:
            init = False

        MAIN_REFERENCES = self.paths["MAIN_REFERENCES"]

        if os.path.exists(os.path.join(os.getcwd(), MAIN_REFERENCES)):
            with open(MAIN_REFERENCES) as target_db:
                bib_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=False,
                    common_strings=True,
                ).parse_file(target_db, partial=True)
        else:
            if init:
                bib_db = BibDatabase()
            else:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), MAIN_REFERENCES
                )

        return bib_db

    def get_record_state_list_from_file_obj(self, file_object):
        return [
            get_record_status_item(record_header_str)
            for record_header_str in self.read_next_record_header_str(file_object)
        ]

    def get_record_state_list(self):
        if not os.path.exists(self.paths["MAIN_REFERENCES"]):
            return []
        return [
            get_record_status_item(record_header_str)
            for record_header_str in self.read_next_record_header_str()
        ]

    def get_states_set(self, record_state_list: list = None):
        if not os.path.exists(self.paths["MAIN_REFERENCES"]):
            return set()
        if record_state_list is None:
            record_state_list = self.get_record_state_list()
        return {el[1] for el in record_state_list}

    def check_precondition(self, process):
        # Special case (not in state model):
        if process.type.name in ["format"]:
            require_clean_repo_general(ignore_pattern=self.paths["MAIN_REFERENCES"])
        else:
            # perform a transition in the Record (state model)
            # to call the corresponding condition check
            condition_check_record = Record(
                "checker", Process.get_source_state(process), self
            )
            class_method = getattr(condition_check_record, process.type.name)
            class_method(condition_check_record)

        self.notified_next_process = process.type
        self.reset_log()

    def run_process(self, process: Process, *args):
        function_name = (
            f"{inspect.getmodule(process.processing_function).__name__}."
            + f"{process.processing_function.__name__}"
        )
        self.logger.info(
            f"ReviewManager: check_precondition({function_name}, "
            + f"a {process.type.name} process)"
        )
        self.check_precondition(process)
        self.logger.info(f"ReviewManager: run {function_name}()")
        process.run(self, *args)
        if self.__git_repo.is_dirty():
            raise DirtyRepoAfterProcessingError
        self.notified_next_process = None

    def get_commit_report(
        self, script_name: str = None, saved_args: dict = None
    ) -> str:
        from review_template import status

        report = "\n\nReport\n\n"

        if script_name is not None:
            script_name = (
                script_name.split(" ")[0]
                + " "
                + script_name.split(" ")[1].replace("_", "-")
            )
            report = report + f"Command\n   {script_name}\n"
        if saved_args is not None:
            repo = None
            for k, v in saved_args.items():
                if isinstance(v, str) or isinstance(v, bool) or isinstance(v, int):
                    report = report + f"     --{k}={v}\n"
                if isinstance(v, git.repo.base.Repo):
                    try:
                        repo = v.head.commit.hexsha
                    except ValueError:
                        pass
                # TODO: should we do anything with the bib_db?
            if not repo:
                try:
                    repo = git.Repo("").head.commit.hexsha
                except ValueError:
                    pass
            # Note: this allows users to see whether the commit was changed!
            if repo:
                report = report + f"   On git repo with version {repo}\n"
            report = report + "\n"

        report = report + "Software"
        rt_version = version("review_template")
        report = (
            report + "\n   - review_template:".ljust(33, " ") + "version " + rt_version
        )
        version("pipeline_validation_hooks")
        report = (
            report
            + "\n   - pre-commit hooks:".ljust(33, " ")
            + "version "
            + version("pipeline_validation_hooks")
        )
        sys_v = sys.version
        report = (
            report
            + "\n   - Python:".ljust(33, " ")
            + "version "
            + sys_v[: sys_v.find(" ")]
        )
        gitv = git.Repo().git
        git_v = gitv.execute(["git", "--version"])
        report = report + "\n   - Git:".ljust(33, " ") + git_v.replace("git ", "")
        stream = os.popen("docker --version")
        docker_v = stream.read()
        report = (
            report
            + "\n   - Docker:".ljust(33, " ")
            + docker_v.replace("Docker ", "").replace("\n", "")
        )
        if script_name is not None:
            ext_script = script_name.split(" ")[0]
            if ext_script != "review_template":
                script_version = version(ext_script)
                report = (
                    report
                    + f"\n   - {ext_script}:".ljust(33, " ")
                    + "version "
                    + script_version
                )

        if "dirty" in report:
            report = (
                report + "\n    * created with a modified version (not reproducible)"
            )

        repo = git.Repo("")
        tree_hash = repo.git.execute(["git", "write-tree"])
        if os.path.exists(self.paths["MAIN_REFERENCES"]):
            report = report + f"\n\nCertified properties for tree {tree_hash}\n"
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
                + "review_template validate --properties "
                + "--commit INSERT_COMMIT_HASH"
            )
        report = report + "\n"

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

        return report

    def get_version_flag(self) -> str:
        flag = ""
        if "dirty" in version("review_template"):
            flag = "*"
        return flag

    def update_status_yaml(self) -> None:
        from review_template import status

        status_freq = status.get_status_freq(self)

        with open("status.yaml", "w") as f:
            yaml.dump(status_freq, f, allow_unicode=True)

        repo = git.Repo()
        repo.index.add(["status.yaml"])

        return

    def reset_log(self) -> None:
        with open("report.log", "r+") as f:
            f.truncate(0)
        return

    def reorder_log(self, IDs: list) -> None:
        # https://docs.python.org/3/howto/logging-cookbook.html
        # #logging-to-a-single-file-from-multiple-processes
        firsts = []
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

        ordered_items = ""
        consumed_items = []
        for ID in IDs:
            for item in items:
                # if f'({ID})' in item:
                if f"{ID}" in item:
                    formatted_item = item
                    if "] prepare(" in formatted_item:
                        formatted_item = f"\n\n{formatted_item}"
                    ordered_items = ordered_items + formatted_item
                    consumed_items.append(item)

        for x in consumed_items:
            if x in items:
                items.remove(x)

        ordered_items = (
            "".join(firsts)
            + "\nDetailed report\n\n"
            + ordered_items.lstrip("\n")
            + "\n\n"
            + "".join(items)
        )
        with open("report.log", "w") as f:
            f.write(ordered_items)
        return

    def create_commit(
        self, msg: str, saved_args: dict, manual_author: bool = False
    ) -> bool:

        if self.__git_repo.is_dirty():

            self.update_status_yaml()
            self.__git_repo.index.add(["status.yaml"])

            hook_skipping = "false"
            if not self.config["DEBUG_MODE"]:
                hook_skipping = "true"

            processing_report = ""
            if os.path.exists("report.log"):
                with open("report.log") as f:
                    line = f.readline()
                    debug_part = False
                    while line:
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
            script = (
                str(caller.f_globals["__name__"]).replace("-", "_").replace(".", " ")
            )
            if "Update pre-commit-config" in msg:
                script = "pre-commit autoupdate"

            if manual_author:
                git_author = git.Actor(self.config["GIT_ACTOR"], self.config["EMAIL"])
            else:
                git_author = git.Actor(f"script:{script}", "")

            self.__git_repo.index.commit(
                msg
                + self.get_version_flag()
                + self.get_commit_report(f"{script}", saved_args)
                + processing_report,
                author=git_author,
                committer=git.Actor(self.config["GIT_ACTOR"], self.config["EMAIL"]),
                skip_hooks=hook_skipping,
            )
            self.logger.info("Created commit")
            self.notified_next_process = None
            self.reset_log()
            if self.__git_repo.is_dirty():
                raise DirtyRepoAfterProcessingError
            return True
        else:
            return False

    def set_IDs(self, bib_db: BibDatabase) -> BibDatabase:
        ID_list = [record["ID"] for record in bib_db.entries]
        for record in bib_db.entries:
            if record["md_status"] in ["imported", "prepared"]:
                old_id = record["ID"]
                new_id = self.generate_ID_blacklist(
                    record, ID_list, record_in_bib_db=True, raise_error=False
                )
                record.update(ID=new_id)
                if old_id != new_id:
                    self.logger.info(f"set_ID({old_id}) to {new_id}")
                ID_list.append(record["ID"])
        return bib_db

    def propagated_ID(self, ID: str) -> bool:

        propagated = False

        if os.path.exists(self.paths["DATA"]):
            # Note: this may be redundant, but just to be sure:
            data = pd.read_csv(self.paths["DATA"], dtype=str)
            if ID in data["ID"].tolist():
                propagated = True

        # TODO: also check data_pages?

        return propagated

    def generate_ID(
        self,
        record: dict,
        bib_db: BibDatabase = None,
        record_in_bib_db: bool = False,
        raise_error: bool = True,
    ) -> str:

        if bib_db is not None:
            ID_blacklist = [record["ID"] for record in bib_db.entries]
        else:
            ID_blacklist = None
        ID = self.generate_ID_blacklist(
            record, ID_blacklist, record_in_bib_db, raise_error
        )
        return ID

    def lpad_multiline(self, s: str, lpad: int) -> str:
        lines = s.splitlines()
        return "\n".join(["".join([" " * lpad]) + line for line in lines])

    def generate_ID_blacklist(
        self,
        record: dict,
        ID_blacklist: list = None,
        record_in_bib_db: bool = False,
        raise_error: bool = True,
    ) -> str:
        from review_template import prepare

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
            authors = prepare.format_author_field(
                record.get("author", record.get("editor", "Anonymous"))
            )
            if " and " in authors:
                authors = authors.split(" and ")
            else:
                authors = [authors]
        else:
            authors = ["Anonymous"]

        # Use family names
        for author in authors:
            if "," in author:
                author = author.split(",")[0]
            else:
                author = author.split(" ")[0]

        ID_PATTERN = self.config["ID_PATTERN"]

        assert ID_PATTERN in ["FIRST_AUTHOR", "THREE_AUTHORS"]
        if "FIRST_AUTHOR" == ID_PATTERN:
            temp_ID = f'{author.replace(" ", "")}{str(record.get("year", "NoYear"))}'

        if "THREE_AUTHORS" == ID_PATTERN:
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

            letters = iter(ascii_lowercase)
            while temp_ID in other_ids:
                try:
                    next_letter = next(letters)
                    if next_letter == "a":
                        temp_ID = temp_ID + next_letter
                    else:
                        temp_ID = temp_ID[:-1] + next_letter
                except StopIteration:
                    letters = iter(ascii_lowercase)
                    pass

        return temp_ID

    def load_search_details(self) -> list:

        if os.path.exists(self.paths["SEARCH_DETAILS"]):
            with open(self.paths["SEARCH_DETAILS"]) as f:
                search_details_df = pd.json_normalize(safe_load(f))
                search_details = search_details_df.to_dict("records")
        else:
            search_details = []
        return search_details

    def save_search_details(self, search_details: list) -> None:
        search_details_df = pd.DataFrame(search_details)
        orderedCols = [
            "filename",
            "search_type",
            "source_name",
            "source_url",
            "search_parameters",
            "comment",
        ]
        orderedCols = orderedCols.append(
            [x for x in search_details_df.columns if x not in orderedCols]
        )
        search_details_df = search_details_df.reindex(columns=orderedCols)

        with open(self.paths["SEARCH_DETAILS"], "w") as f:
            yaml.dump(
                json.loads(search_details_df.to_json(orient="records")),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
        return

    def get_bib_files(self) -> None:
        search_dir = os.path.join(os.getcwd(), "search/")
        return [
            os.path.join(search_dir, x)
            for x in os.listdir(search_dir)
            if x.endswith(".bib")
        ]

    def get_nr_in_bib(self, file_path: str) -> int:

        number_in_bib = 0
        with open(file_path) as f:
            line = f.readline()
            while line:
                # Note: the '﻿' occured in some bibtex files
                # (e.g., Publish or Perish exports)
                if line.replace("﻿", "").lstrip()[:1] == "@":
                    if not "@comment" == line.replace("﻿", "").lstrip()[:8].lower():
                        number_in_bib += 1
                line = f.readline()

        return number_in_bib

    def save_bib_file(self, bib_db: BibDatabase, target_file: str = None) -> None:

        if target_file is None:
            target_file = self.paths["MAIN_REFERENCES"]

        try:
            bib_db.comments.remove("% Encoding: UTF-8")
        except ValueError:
            pass

        bibtex_str = bibtexparser.dumps(bib_db, get_bibtex_writer())

        with open(target_file, "w") as out:
            out.write(bibtex_str)

        return

    def require_clean_repo(self, ignore_pattern: str = None) -> bool:
        return require_clean_repo_general(self.__git_repo, ignore_pattern)

    def build_docker_images(self) -> None:

        client = docker.from_env()

        repo_tags = [x.attrs.get("RepoTags", "") for x in client.images.list()]
        repo_tags = [
            item[: item.find(":")] for sublist in repo_tags for item in sublist
        ]

        if "bibself" not in repo_tags:
            self.logger.info("Building bibself Docker image...")
            filedata = pkgutil.get_data(__name__, "../docker/bibself/Dockerfile")
            fileobj = io.BytesIO(filedata)
            client.images.build(fileobj=fileobj, tag="bibself:latest")

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

    def read_next_record_header_str(
        self, file_object=None, HEADER_LENGTH: int = None
    ) -> str:
        if HEADER_LENGTH is None:
            HEADER_LENGTH = 9
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
                if first_entry_processed:
                    yield data
                    header_line_count = 0
                else:
                    first_entry_processed = True
                data = line
        yield data

    def read_next_record_str(self, file_object=None) -> str:
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

    def read_next_record(self) -> dict:
        records = []
        with open(self.paths["MAIN_REFERENCES"]) as f:
            for record_string in self.read_next_record_str(f):
                parser = BibTexParser(customization=convert_to_unicode)
                db = bibtexparser.loads(record_string, parser=parser)
                record = db.entries[0]
                records.append(record)
        yield from records
