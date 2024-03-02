#!/usr/bin/env python3
"""Functionality for data/records.bib and git repository."""
from __future__ import annotations

import io
import itertools
import os
import re
import string
import time
import typing
from copy import deepcopy
from pathlib import Path
from random import randint
from typing import Optional

import git
from git import InvalidGitRepositoryError
from git.exc import GitCommandError
from tqdm import tqdm

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.ops.load_utils_bib
import colrev.record
import colrev.settings
from colrev.constants import ExitCodes
from colrev.constants import Fields
from colrev.constants import FieldValues


# pylint: disable=too-many-public-methods
# pylint: disable=too-many-lines


class Dataset:
    """The CoLRev dataset (records and their history in git)"""

    RECORDS_FILE_RELATIVE = Path("data/records.bib")
    # Ensure the path uses forward slashes, which is compatible with Git's path handling
    RECORDS_FILE_RELATIVE_GIT = str(RECORDS_FILE_RELATIVE).replace("\\", "/")
    RECORDS_FIELD_ORDER = [
        Fields.ORIGIN,  # must be in second line
        Fields.STATUS,
        Fields.MD_PROV,
        Fields.D_PROV,
        Fields.PDF_ID,
        Fields.SCREENING_CRITERIA,
        Fields.FILE,  # Note : do not change this order (parsers rely on it)
        Fields.PRESCREEN_EXCLUSION,
        Fields.DOI,
        Fields.GROBID_VERSION,
        Fields.DBLP_KEY,
        Fields.SEMANTIC_SCHOLAR_ID,
        Fields.WEB_OF_SCIENCE_ID,
        Fields.AUTHOR,
        Fields.BOOKTITLE,
        Fields.JOURNAL,
        Fields.TITLE,
        Fields.YEAR,
        Fields.VOLUME,
        Fields.NUMBER,
        Fields.PAGES,
        Fields.EDITOR,
        Fields.PUBLISHER,
        Fields.URL,
        Fields.ABSTRACT,
    ]

    GIT_IGNORE_FILE_RELATIVE = Path(".gitignore")
    DEFAULT_GIT_IGNORE_ITEMS = [
        ".history",
        ".colrev",
        ".corrections",
        ".report.log",
        "__pycache__",
        "*.bib.sav",
        "venv",
        "output",
        "data/pdfs",
        "data/pdf_get_man/missing_pdf_files.csv",
        "data/.tei/",
        "data/prep_man/records_prep_man.bib",
        "data/prep/",
        "data/dedupe/",
        "data/data/sample_references.bib",
    ]
    DEPRECATED_GIT_IGNORE_ITEMS = [
        "missing_pdf_files.csv",
        "manual_cleansing_statistics.csv",
        ".references_learned_settings",
        "pdfs",
        ".tei",
        "data.csv",
        "requests_cache.sqlite",
    ]

    records_file: Path
    _git_repo: git.Repo

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.review_manager = review_manager
        self.records_file = review_manager.path / self.RECORDS_FILE_RELATIVE
        self.git_ignore_file = review_manager.path / self.GIT_IGNORE_FILE_RELATIVE

        try:
            # In most cases, the repo should exist
            # due to review_manager._get_project_home_dir()
            self._git_repo = git.Repo(self.review_manager.path)
        except InvalidGitRepositoryError as exc:
            msg = "Not a CoLRev/git repository. Run\n    colrev init"
            raise colrev_exceptions.RepoSetupError(msg) from exc

        self.update_gitignore(
            add=self.DEFAULT_GIT_IGNORE_ITEMS, remove=self.DEPRECATED_GIT_IGNORE_ITEMS
        )

    def update_gitignore(
        self, *, add: typing.Optional[list] = None, remove: typing.Optional[list] = None
    ) -> None:
        """Update the gitignore file by adding or removing particular paths"""
        # The following may print warnings...

        if self.git_ignore_file.is_file():
            gitignore_content = self.git_ignore_file.read_text(encoding="utf-8")
        else:
            gitignore_content = ""
        ignored_items = gitignore_content.splitlines()
        if remove:
            ignored_items = [x for x in ignored_items if x not in remove]
        if add:
            ignored_items = ignored_items + [
                str(a) for a in add if str(a) not in ignored_items
            ]

        with self.git_ignore_file.open("w", encoding="utf-8") as file:
            file.write("\n".join(ignored_items) + "\n")
        self.add_changes(path=self.git_ignore_file)

    def get_origin_state_dict(
        self, *, file_object: Optional[io.StringIO] = None
    ) -> dict:
        """Get the origin_state_dict (to determine state transitions efficiently)

        {'30_example_records.bib/Staehr2010': <RecordState.pdf_not_available: 10>,}
        """

        current_origin_states_dict = {}
        if self.records_file.is_file():
            for record_header_item in self._read_record_header_items(
                file_object=file_object
            ):
                for origin in record_header_item[Fields.ORIGIN]:
                    current_origin_states_dict[origin] = record_header_item[
                        Fields.STATUS
                    ]
        return current_origin_states_dict

    def get_committed_origin_state_dict(self) -> dict:
        """Get the committed origin_state_dict"""

        filecontents = self._get_last_records_filecontents()
        committed_origin_state_dict = self.get_origin_state_dict(
            file_object=io.StringIO(filecontents.decode("utf-8"))
        )
        return committed_origin_state_dict

    def load_records_from_history(
        self, *, commit_sha: str = ""
    ) -> typing.Iterator[dict]:
        """
        Iterates through Git history, yielding records file contents as dictionaries.

        Starts iteration from a provided commit SHA.
        Skips commits where the records file is unchanged.
        Useful for tracking dataset changes over time.

        Parameters:
            commit_sha (str, optional): Start iteration from this commit SHA.
            Defaults to beginning of Git history if not provided.

        Yields:
            dict: Records file contents at a specific Git history point, as a dictionary.
        """

        reached_target_commit = False  # if no commit_sha provided
        for current_commit in self._git_repo.iter_commits():

            # Skip all commits before the specified commit_sha, if provided
            if commit_sha and not reached_target_commit:
                if commit_sha != current_commit.hexsha:
                    # Move to the next commit
                    continue
                reached_target_commit = True

            # Read and parse the records file from the current commit
            filecontents = (
                current_commit.tree / self.RECORDS_FILE_RELATIVE_GIT
            ).data_stream.read()

            bib_loader = colrev.ops.load_utils_bib.BIBLoader(
                load_string=filecontents.decode("utf-8"),
                logger=self.review_manager.logger,
                force_mode=self.review_manager.force_mode,
            )
            records_dict = bib_loader.load_bib_file(check_bib_file=False)

            if records_dict:
                yield records_dict

    def get_changed_records(self, *, target_commit: str) -> typing.List[dict]:
        """Get the records that changed in a selected commit"""

        revlist = (
            (
                commit.hexsha,
                (commit.tree / self.RECORDS_FILE_RELATIVE_GIT).data_stream.read(),
            )
            for commit in self._git_repo.iter_commits(
                paths=str(self.RECORDS_FILE_RELATIVE)
            )
        )
        found = False
        records_dict, prior_records_dict = {}, {}
        for commit, filecontents in list(revlist):
            if found:  # load the records_file_relative in the following commit
                prior_records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=filecontents.decode("utf-8")
                )
                break
            if commit == target_commit:
                records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=filecontents.decode("utf-8")
                )
                found = True

        # determine which records have been changed (prepared or merged)
        # in the target_commit
        for record in records_dict.values():
            prior_record_l = [
                rec
                for rec in prior_records_dict.values()
                if any(x in record[Fields.ORIGIN] for x in rec[Fields.ORIGIN])
            ]
            if prior_record_l:
                prior_record = prior_record_l[0]
                # Note: the following is an exact comparison of all fields
                if record != prior_record:
                    record.update(changed_in_target_commit="True")

        return list(records_dict.values())

    @classmethod
    def _load_field_dict(cls, *, value: str, field: str) -> dict:
        # pylint: disable=too-many-branches

        assert field in [
            Fields.MD_PROV,
            Fields.D_PROV,
        ], f"error loading dict_field: {field}"

        return_dict = {}
        if field == Fields.MD_PROV:
            if value[:7] == FieldValues.CURATED:
                source = value[value.find(":") + 1 : value[:-1].rfind(";")]
                return_dict[FieldValues.CURATED] = {
                    "source": source,
                    "note": "",
                }

            elif value != "":
                # Pybtex automatically replaces \n in fields.
                # For consistency, we also do that for header_only mode:
                if "\n" in value:
                    value = value.replace("\n", " ")
                items = [x.lstrip() + ";" for x in (value + " ").split("; ") if x != ""]

                for item in items:
                    key_source = item[: item[:-1].rfind(";")]
                    assert (
                        ":" in key_source
                    ), f"problem with masterdata_provenance_item {item}"
                    note = item[item[:-1].rfind(";") + 1 : -1]
                    key, source = key_source.split(":", 1)
                    # key = key.rstrip().lstrip()
                    return_dict[key] = {
                        "source": source,
                        "note": note,
                    }

        elif field == Fields.D_PROV:
            if value != "":
                # Note : pybtex replaces \n upon load
                for item in (value + " ").split("; "):
                    if item == "":
                        continue
                    item += ";"  # removed by split
                    key_source = item[: item[:-1].rfind(";")]
                    note = item[item[:-1].rfind(";") + 1 : -1]
                    assert (
                        ":" in key_source
                    ), f"problem with data_provenance_item {item}"
                    key, source = key_source.split(":", 1)
                    return_dict[key] = {
                        "source": source,
                        "note": note,
                    }

        return return_dict

    def _parse_k_v(self, item_string: str) -> tuple:
        if " = " in item_string:
            key, value = item_string.split(" = ", 1)
        else:
            key = Fields.ID
            value = item_string.split("{")[1]

        key = key.lstrip().rstrip()
        value = value.lstrip().rstrip().lstrip("{").rstrip("},")
        if key == Fields.ORIGIN:
            value_list = value.replace("\n", "").split(";")
            value_list = [x.lstrip(" ").rstrip(" ") for x in value_list if x]
            return key, value_list
        if key == Fields.STATUS:
            return key, colrev.record.RecordState[value]
        if key == Fields.MD_PROV:
            return key, self._load_field_dict(value=value, field=key)
        if key == Fields.FILE:
            return key, Path(value)

        return key, value

    def _read_record_header_items(
        self, *, file_object: Optional[typing.TextIO] = None
    ) -> list:
        # Note : more than 10x faster than the pybtex part of load_records_dict()

        # pylint: disable=consider-using-with
        if file_object is None:
            file_object = open(self.records_file, encoding="utf-8")

        # Fields required
        default = {
            Fields.ID: "NA",
            Fields.ORIGIN: "NA",
            Fields.STATUS: "NA",
            Fields.FILE: "NA",
            Fields.SCREENING_CRITERIA: "NA",
            Fields.MD_PROV: "NA",
        }
        number_required_header_items = len(default)

        record_header_item = default.copy()
        item_count, item_string, record_header_items = (
            0,
            "",
            [],
        )
        while True:
            line = file_object.readline()
            if not line:
                break

            if line[:1] == "%" or line == "\n":
                continue

            if item_count > number_required_header_items or "}" == line:
                record_header_items.append(record_header_item)
                record_header_item = default.copy()
                item_count = 0
                continue

            if "@" in line[:2] and record_header_item[Fields.ID] != "NA":
                record_header_items.append(record_header_item)
                record_header_item = default.copy()
                item_count = 0

            item_string += line
            if "}," in line or "@" in line[:2]:
                key, value = self._parse_k_v(item_string)
                if key == Fields.MD_PROV:
                    if value == "NA":
                        value = {}
                if value == "NA":
                    item_string = ""
                    continue
                item_string = ""
                if key in record_header_item:
                    item_count += 1
                    record_header_item[key] = value

        if record_header_item[Fields.ORIGIN] != "NA":
            record_header_items.append(record_header_item)

        return [
            {k: v for k, v in record_header_item.items() if "NA" != v}
            for record_header_item in record_header_items
        ]

    def load_records_dict(
        self,
        *,
        load_str: Optional[str] = None,
        header_only: bool = False,
    ) -> dict:
        """Load the records

        - requires review_manager.notify(...)

        header_only:

        {"Staehr2010": {'ID': 'Staehr2010',
        'colrev_origin': ['30_example_records.bib/Staehr2010'],
        'colrev_status': <RecordState.md_imported: 2>,
        'screening_criteria': 'criterion1=in;criterion2=out',
        'file': PosixPath('data/pdfs/Smith2000.pdf'),
        'Fields.MD_PROV': {Fields.AUTHOR:{"source":"...", "note":"..."}}},
        }
        """

        if self.review_manager.notified_next_operation is None:
            raise colrev_exceptions.ReviewManagerNotNotifiedError()

        if header_only:
            # Note : currently not parsing screening_criteria to settings.ScreeningCriterion
            # to optimize performance
            record_header_list = (
                self._read_record_header_items() if self.records_file.is_file() else []
            )
            record_header_dict = {r[Fields.ID]: r for r in record_header_list}
            return record_header_dict

        if load_str:
            # Fix missing comma after fields
            load_str = re.sub(r"(.)}\n", r"\g<1>},\n", load_str)
            bib_loader = colrev.ops.load_utils_bib.BIBLoader(
                load_string=load_str,
                logger=self.review_manager.logger,
                force_mode=self.review_manager.force_mode,
            )
            records_dict = bib_loader.load_bib_file(check_bib_file=False)

        elif self.records_file.is_file():
            bib_loader = colrev.ops.load_utils_bib.BIBLoader(
                source_file=self.records_file,
                logger=self.review_manager.logger,
                force_mode=self.review_manager.force_mode,
            )
            records_dict = bib_loader.load_bib_file(check_bib_file=False)

        else:
            records_dict = {}

        return records_dict

    @classmethod
    def parse_bibtex_str(
        cls,
        *,
        recs_dict_in: dict,
    ) -> str:
        """Parse a records_dict to a BiBTex string"""

        # Note: we need a deepcopy because the parsing modifies dicts
        recs_dict = deepcopy(recs_dict_in)

        def format_field(field: str, value: str) -> str:
            padd = " " * max(0, 28 - len(field))
            return f",\n   {field} {padd} = {{{value}}}"

        bibtex_str = ""
        first = True
        for record_id, record_dict in sorted(recs_dict.items()):
            if not first:
                bibtex_str += "\n"
            first = False

            bibtex_str += f"@{record_dict[Fields.ENTRYTYPE]}{{{record_id}"

            record = colrev.record.Record(data=record_dict)
            record_dict = record.get_data(stringify=True)

            for ordered_field in cls.RECORDS_FIELD_ORDER:
                if ordered_field in record_dict:
                    if record_dict[ordered_field] == "":
                        continue
                    bibtex_str += format_field(
                        ordered_field, record_dict[ordered_field]
                    )

            for key in sorted(record_dict.keys()):
                if key in cls.RECORDS_FIELD_ORDER + [Fields.ID, Fields.ENTRYTYPE]:
                    continue

                bibtex_str += format_field(key, record_dict[key])

            bibtex_str += ",\n}\n"

        return bibtex_str

    def save_records_dict_to_file(
        self, *, records: dict, save_path: Path, add_changes: bool = True
    ) -> None:
        """Save the records dict to specified file"""
        # Note : this classmethod function can be called by CoLRev scripts
        # operating outside a CoLRev repo (e.g., sync)

        bibtex_str = self.parse_bibtex_str(recs_dict_in=records)

        with open(save_path, "w", encoding="utf-8") as out:
            out.write(bibtex_str + "\n")

        if not add_changes:
            return
        if save_path == self.records_file:
            self._add_record_changes()
        else:
            self.add_changes(path=save_path)

    def _save_record_list_by_id(
        self, *, records: dict, append_new: bool = False
    ) -> None:
        # Note : currently no use case for append_new=True??

        parsed = self.parse_bibtex_str(recs_dict_in=records)
        record_list = [
            {
                Fields.ID: item[item.find("{") + 1 : item.find(",")],
                "record": "@" + item + "\n",
            }
            for item in parsed.split("\n@")
        ]
        # Correct the first item
        record_list[0]["record"] = "@" + record_list[0]["record"][2:]

        current_id_str = "NOTSET"
        if self.records_file.is_file():
            with open(self.records_file, "r+b") as file:
                seekpos = file.tell()
                line = file.readline()
                while line:
                    if b"@" in line[:3]:
                        current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                        current_id_str = current_id.decode("utf-8")
                    if current_id_str in [x[Fields.ID] for x in record_list]:
                        replacement = [
                            x["record"]
                            for x in record_list
                            if x[Fields.ID] == current_id_str
                        ][0]
                        record_list = [
                            x for x in record_list if x[Fields.ID] != current_id_str
                        ]
                        line = file.readline()
                        while (
                            b"@" not in line[:3] and line
                        ):  # replace: drop the current record
                            line = file.readline()
                        remaining = line + file.read()
                        file.seek(seekpos)
                        file.write(replacement.encode("utf-8"))
                        seekpos = file.tell()
                        file.flush()
                        os.fsync(file)
                        file.write(remaining)
                        file.truncate()  # if the replacement is shorter...
                        file.seek(seekpos)

                    seekpos = file.tell()
                    line = file.readline()

        if len(record_list) > 0:
            if append_new:
                with open(self.records_file, "a", encoding="utf8") as m_refs:
                    for item in record_list:
                        m_refs.write(item["record"])
            else:
                self.review_manager.report_logger.error(
                    "records not written to file: "
                    f"{[x[Fields.ID] for x in record_list]}"
                )

        self._add_record_changes()

    def save_records_dict(
        self, *, records: dict, partial: bool = False, add_changes: bool = True
    ) -> None:
        """Save the records dict in RECORDS_FILE"""

        if partial:
            self._save_record_list_by_id(records=records)
            return
        self.save_records_dict_to_file(
            records=records, save_path=self.records_file, add_changes=add_changes
        )

    def read_next_record(
        self, *, conditions: Optional[list] = None
    ) -> typing.Iterator[dict]:
        """Read records (Iterator) based on condition"""

        # Note : matches conditions connected with 'OR'
        record_dict = self.load_records_dict()

        records = []
        for _, record in record_dict.items():
            if conditions is not None:
                for condition in conditions:
                    for key, value in condition.items():
                        if str(value) == str(record[key]):
                            records.append(record)
            else:
                records.append(record)
        yield from records

    def get_format_report(self) -> dict:
        """Get format report"""

        if not self.records_file.is_file():
            return {"status": ExitCodes.SUCCESS, "msg": "Everything ok."}

        if not self.records_changed() and not self.review_manager.force_mode:
            return {"status": ExitCodes.SUCCESS, "msg": "Everything ok."}

        try:
            colrev.operation.FormatOperation(
                review_manager=self.review_manager
            )  # to notify
            quality_model = self.review_manager.get_qm()
            records = self.load_records_dict()
            for record_dict in records.values():
                if Fields.STATUS not in record_dict:
                    print(
                        f"Error: no status field in record ({record_dict[Fields.ID]})"
                    )
                    continue

                record = colrev.record.PrepRecord(data=record_dict)
                if record_dict[Fields.STATUS] in [
                    colrev.record.RecordState.md_needs_manual_preparation,
                ]:
                    record.run_quality_model(qm=quality_model)

                if record_dict[Fields.STATUS] == colrev.record.RecordState.pdf_prepared:
                    record.reset_pdf_provenance_notes()

            self.save_records_dict(records=records)
            changed = self.RECORDS_FILE_RELATIVE in [
                r.a_path for r in self._git_repo.index.diff(None)
            ]
            self.review_manager.update_status_yaml()
            self.review_manager.load_settings()
            self.review_manager.save_settings()
        except (
            colrev_exceptions.UnstagedGitChangesError,
            colrev_exceptions.StatusFieldValueError,
        ) as exc:
            return {"status": ExitCodes.FAIL, "msg": f"{type(exc).__name__}: {exc}"}

        if changed:
            return {"status": ExitCodes.FAIL, "msg": "records file formatted"}

        return {"status": ExitCodes.SUCCESS, "msg": "Everything ok."}

    # ID creation, update and lookup ---------------------------------------

    def _generate_temp_id(
        self, *, local_index: colrev.env.local_index.LocalIndex, record_dict: dict
    ) -> str:
        # pylint: disable=too-many-branches

        try:
            retrieved_record = local_index.retrieve(record_dict=record_dict)
            temp_id = retrieved_record[Fields.ID]

            # Do not use IDs from local_index for curated_metadata repositories
            if self.review_manager.settings.is_curated_masterdata_repo():
                raise colrev_exceptions.RecordNotInIndexException()

        except (
            colrev_exceptions.RecordNotInIndexException,
            colrev_exceptions.NotEnoughDataToIdentifyException,
        ):
            if record_dict.get(Fields.AUTHOR, record_dict.get(Fields.EDITOR, "")) != "":
                authors_string = record_dict.get(
                    Fields.AUTHOR, record_dict.get(Fields.EDITOR, "Anonymous")
                )
                authors = colrev.record.PrepRecord.format_author_field(
                    input_string=authors_string
                ).split(" and ")
            else:
                authors = ["Anonymous"]

            # Use family names
            for author in authors:
                if "," in author:
                    author = author.split(",", maxsplit=1)[0]
                else:
                    author = author.split(" ", maxsplit=1)[0]

            id_pattern = self.review_manager.settings.project.id_pattern
            if colrev.settings.IDPattern.first_author_year == id_pattern:
                first_author = authors[0].split(",")[0].replace(" ", "")
                temp_id = f'{first_author}{str(record_dict.get(Fields.YEAR, "NoYear"))}'
            elif colrev.settings.IDPattern.three_authors_year == id_pattern:
                temp_id = ""
                indices = len(authors)
                if len(authors) > 3:
                    indices = 3
                for ind in range(0, indices):
                    temp_id = temp_id + f'{authors[ind].split(",")[0].replace(" ", "")}'
                if len(authors) > 3:
                    temp_id = temp_id + "EtAl"
                temp_id = temp_id + str(record_dict.get(Fields.YEAR, "NoYear"))

            if temp_id.isupper():
                temp_id = temp_id.capitalize()
            # Replace special characters
            # (because IDs may be used as file names)
            temp_id = colrev.env.utils.remove_accents(input_str=temp_id)
            temp_id = re.sub(r"\(.*\)", "", temp_id)
            temp_id = re.sub("[^0-9a-zA-Z]+", "", temp_id)

        return temp_id

    def _generate_next_unique_id(
        self,
        *,
        temp_id: str,
        existing_ids: list,
    ) -> str:
        """Get the next unique ID"""

        order = 0
        letters = list(string.ascii_lowercase)
        next_unique_id = temp_id
        appends: list = []
        while next_unique_id.lower() in [i.lower() for i in existing_ids]:
            if len(appends) == 0:
                order += 1
                appends = list(itertools.product(letters, repeat=order))
            next_unique_id = temp_id + "".join(list(appends.pop(0)))
        temp_id = next_unique_id
        return temp_id

    def propagated_id(self, *, record_id: str) -> bool:
        """Check whether an ID is propagated (i.e., its record's status is beyond md_processed)"""

        for record in self.load_records_dict(header_only=True).values():
            if record[Fields.ID] == record_id:
                if record[Fields.STATUS] in colrev.record.RecordState.get_post_x_states(
                    state=colrev.record.RecordState.md_processed
                ):
                    return True

        return False

    def _generate_id(
        self,
        *,
        local_index: colrev.env.local_index.LocalIndex,
        record_dict: dict,
        existing_ids: Optional[list] = None,
    ) -> str:
        """Generate a blacklist to avoid setting duplicate IDs"""

        # Only change IDs that are before md_processed
        if record_dict[Fields.STATUS] in colrev.record.RecordState.get_post_x_states(
            state=colrev.record.RecordState.md_processed
        ):
            raise colrev_exceptions.PropagatedIDChange([record_dict[Fields.ID]])
        # Alternatively, we could change IDs except for those
        # that have been propagated to the
        # screen or data will not be replaced
        # (this would break the chain of evidence)

        temp_id = self._generate_temp_id(
            local_index=local_index, record_dict=record_dict
        )

        if existing_ids:
            temp_id = self._generate_next_unique_id(
                temp_id=temp_id,
                existing_ids=existing_ids,
            )

        return temp_id

    def set_ids(
        self, *, records: Optional[dict] = None, selected_ids: Optional[list] = None
    ) -> dict:
        """Set the IDs of records according to predefined formats or
        according to the LocalIndex"""
        # pylint: disable=redefined-outer-name

        local_index = self.review_manager.get_local_index()

        if records is None:
            records = {}

        if len(records) == 0:
            records = self.load_records_dict()

        id_list = list(records.keys())

        for record_id in tqdm(list(records.keys())):
            try:
                record_dict = records[record_id]
                if selected_ids is not None:
                    if record_id not in selected_ids:
                        continue
                if (
                    record_dict[Fields.STATUS]
                    not in [
                        colrev.record.RecordState.md_imported,
                        colrev.record.RecordState.md_prepared,
                    ]
                    and not self.review_manager.force_mode
                ):
                    continue
                old_id = record_id

                temp_stat = record_dict[Fields.STATUS]
                if selected_ids:
                    record = colrev.record.Record(data=record_dict)
                    record.set_status(
                        target_state=colrev.record.RecordState.md_prepared
                    )
                new_id = self._generate_id(
                    local_index=local_index,
                    record_dict=record_dict,
                    existing_ids=[x for x in id_list if x != record_id],
                )
                if selected_ids:
                    record = colrev.record.Record(data=record_dict)
                    record.set_status(target_state=temp_stat)

                id_list.append(new_id)
                if old_id != new_id:
                    # We need to insert the a new element into records
                    # to make sure that the IDs are actually saved
                    record_dict.update(ID=new_id)
                    records[new_id] = record_dict
                    del records[old_id]
                    self.review_manager.report_logger.info(
                        f"set_ids({old_id}) to {new_id}"
                    )
                    if old_id in id_list:
                        id_list.remove(old_id)
            except colrev_exceptions.PropagatedIDChange as exc:
                print(exc)

        self.save_records_dict(records=records)
        self._add_record_changes()

        return records

    # GIT operations -----------------------------------------------

    def get_repo(self) -> git.Repo:
        """Get the git repository object (requires review_manager.notify(...))"""

        if self.review_manager.notified_next_operation is None:
            raise colrev_exceptions.ReviewManagerNotNotifiedError()
        return self._git_repo

    def has_record_changes(self, *, change_type: str = "all") -> bool:
        """Check whether the records have changes"""
        return self.has_changes(
            relative_path=Path(self.RECORDS_FILE_RELATIVE_GIT), change_type=change_type
        )

    def has_changes(self, *, relative_path: Path, change_type: str = "all") -> bool:
        """Check whether the relative path (or the git repository) has changes"""

        assert change_type in [
            "all",
            "staged",
            "unstaged",
        ], "Invalid change_type specified"

        # Check if the repository has at least one commit
        try:
            bool(self._git_repo.head.commit)
        except ValueError:
            return True  # Repository has no commit

        diff_index = [item.a_path for item in self._git_repo.index.diff(None)]
        diff_head = [item.a_path for item in self._git_repo.head.commit.diff()]
        unstaged_changes = diff_index + self._git_repo.untracked_files

        # Ensure the path uses forward slashes, which is compatible with Git's path handling
        path_str = str(relative_path).replace("\\", "/")

        if change_type == "all":
            path_changed = path_str in diff_index + diff_head
        elif change_type == "staged":
            path_changed = path_str in diff_head
        elif change_type == "unstaged":
            path_changed = path_str in unstaged_changes
        return path_changed

    def _sleep_util_git_unlocked(self) -> None:
        i = 0
        while (
            self.review_manager.path / Path(".git/index.lock")
        ).is_file():  # pragma: no cover
            i += 1
            time.sleep(randint(1, 50) * 0.1)  # nosec
            if i > 5:
                print("Waiting for previous git operation to complete")
            elif i > 30:
                raise colrev_exceptions.GitNotAvailableError()

    def add_changes(
        self, *, path: Path, remove: bool = False, ignore_missing: bool = False
    ) -> None:
        """Add changed file to git"""

        if path.is_absolute():
            path = path.relative_to(self.review_manager.path)

        self._sleep_util_git_unlocked()

        try:
            if remove:
                self._git_repo.index.remove([str(path)])
            else:
                self._git_repo.index.add([str(path)])
        except FileNotFoundError as exc:
            if not ignore_missing:
                raise exc

    def get_untracked_files(self) -> list:
        """Get the files that are untracked by git"""

        return [Path(x) for x in self._git_repo.untracked_files]

    def _get_last_records_filecontents(self) -> bytes:
        # Ensure the path uses forward slashes, which is compatible with Git's path handling

        revlist = (
            (
                commit.hexsha,
                (commit.tree / self.RECORDS_FILE_RELATIVE_GIT).data_stream.read(),
            )
            for commit in self._git_repo.iter_commits(
                paths=str(self.RECORDS_FILE_RELATIVE_GIT)
            )
        )
        filecontents = list(revlist)[0][1]
        return filecontents

    def records_changed(self) -> bool:
        """Check whether the records were changed"""
        main_recs_changed = str(self.RECORDS_FILE_RELATIVE_GIT) in [
            item.a_path for item in self._git_repo.index.diff(None)
        ] + [x.a_path for x in self._git_repo.head.commit.diff()]
        return main_recs_changed

    # pylint: disable=too-many-arguments
    def create_commit(
        self,
        *,
        msg: str,
        manual_author: bool = False,
        script_call: str = "",
        saved_args: Optional[dict] = None,
        skip_status_yaml: bool = False,
        skip_hooks: bool = True,
    ) -> bool:
        """Create a commit (including a commit report)"""
        # pylint: disable=import-outside-toplevel
        # pylint: disable=redefined-outer-name
        import colrev.ops.commit

        if self.review_manager.exact_call and script_call == "":
            script_call = self.review_manager.exact_call

        commit = colrev.ops.commit.Commit(
            review_manager=self.review_manager,
            msg=msg,
            manual_author=manual_author,
            script_name=script_call,
            saved_args=saved_args,
            skip_hooks=skip_hooks,
        )
        ret = commit.create(skip_status_yaml=skip_status_yaml)
        return ret

    def file_in_history(self, *, filepath: Path) -> bool:
        """Check whether a file is in the git history"""
        return str(filepath) in [
            o.path for o in self._git_repo.head.commit.tree.traverse()
        ]

    def get_commit_message(self, *, commit_nr: int) -> str:
        """Get the commit message for commit #"""
        master = self._git_repo.head.reference
        assert commit_nr == 0  # extension : implement other cases
        if commit_nr == 0:
            cmsg = master.commit.message
        return cmsg

    def _add_record_changes(self) -> None:
        """Add changes in records to git"""
        self._sleep_util_git_unlocked()
        self._git_repo.index.add([str(self.RECORDS_FILE_RELATIVE)])

    def add_setting_changes(self) -> None:
        """Add changes in settings to git"""
        self._sleep_util_git_unlocked()

        self._git_repo.index.add([str(self.review_manager.SETTINGS_RELATIVE)])

    def has_untracked_search_records(self) -> bool:
        """Check whether there are untracked search records"""
        return any(
            str(self.review_manager.SEARCHDIR_RELATIVE) in str(untracked_file)
            for untracked_file in self.get_untracked_files()
        )

    def stash_unstaged_changes(self) -> bool:
        """Stash unstaged changes"""
        ret = self._git_repo.git.stash("push", "--keep-index")
        return "No local changes to save" != ret

    def reset_log_if_no_changes(self) -> None:
        """Reset the report log file if there are not changes"""
        if not self._git_repo.is_dirty():
            self.review_manager.reset_report_logger()

    def get_last_commit_sha(self) -> str:  # pragma: no cover
        """Get the last commit sha"""
        return str(self._git_repo.head.commit.hexsha)

    def get_tree_hash(self) -> str:  # pragma: no cover
        """Get the current tree hash"""
        tree_hash = self._git_repo.git.execute(["git", "write-tree"])
        return str(tree_hash)

    def _get_remote_commit_differences(self) -> list:  # pragma: no cover
        origin = self._git_repo.remotes.origin
        if origin.exists():
            try:
                origin.fetch()
            except GitCommandError:
                return [-1, -1]

        nr_commits_behind, nr_commits_ahead = -1, -1
        if self._git_repo.active_branch.tracking_branch() is not None:
            branch_name = str(self._git_repo.active_branch)
            tracking_branch_name = str(self._git_repo.active_branch.tracking_branch())
            # self.review_manager.logger.debug(f"{branch_name} - {tracking_branch_name}")

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = self._git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = self._git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

        return [nr_commits_behind, nr_commits_ahead]

    def behind_remote(self) -> bool:  # pragma: no cover
        """Check whether the repository is behind the remote"""
        nr_commits_behind = 0
        connected_remote = 0 != len(self._git_repo.remotes)
        if connected_remote:
            origin = self._git_repo.remotes.origin
            if origin.exists():
                (
                    nr_commits_behind,
                    _,
                ) = self._get_remote_commit_differences()
        if nr_commits_behind > 0:
            return True
        return False

    def remote_ahead(self) -> bool:  # pragma: no cover
        """Check whether the remote is ahead"""
        connected_remote = 0 != len(self._git_repo.remotes)
        if connected_remote:
            origin = self._git_repo.remotes.origin
            if origin.exists():
                (
                    _,
                    nr_commits_ahead,
                ) = self._get_remote_commit_differences()
        if nr_commits_ahead > 0:
            return True
        return False

    def pull_if_repo_clean(self) -> None:  # pragma: no cover
        """Pull project if repository is clean"""
        if not self._git_repo.is_dirty():
            origin = self._git_repo.remotes.origin
            origin.pull()

    def get_remote_url(self) -> str:  # pragma: no cover
        """Get the remote url"""
        remote_url = "NA"
        for remote in self._git_repo.remotes:
            if remote.name == "origin":
                remote_url = remote.url
        return remote_url
