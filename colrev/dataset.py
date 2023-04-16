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
from typing import Optional

import git
import pybtex.errors
from git.exc import GitCommandError
from git.exc import InvalidGitRepositoryError
from pybtex.database import Person
from pybtex.database.input import bibtex
from tqdm import tqdm

import colrev.env.language_service
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record
import colrev.settings

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager

# pylint: disable=too-many-public-methods
# pylint: disable=too-many-lines


class Dataset:
    """The CoLRev dataset (records and their history in git)"""

    RECORDS_FILE_RELATIVE = Path("data/records.bib")
    GIT_IGNORE_FILE_RELATIVE = Path(".gitignore")
    DEFAULT_GIT_IGNORE_ITEMS = [
        "*.bib.sav",
        "venv",
        ".corrections",
        "data/pdfs",
        ".report.log",
        "__pycache__",
        "output",
        "data/pdf_get_man/missing_pdf_files.csv",
        "data/.tei/",
        "data/prep_man/records_prep_man.bib",
        "data/prep/",
        "data/dedupe/",
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
    __git_repo: git.Repo

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.review_manager = review_manager
        self.records_file = review_manager.path / self.RECORDS_FILE_RELATIVE
        self.git_ignore_file = review_manager.path / self.GIT_IGNORE_FILE_RELATIVE

        try:
            self.__git_repo = git.Repo(self.review_manager.path)
        except InvalidGitRepositoryError as exc:
            msg = "Not a CoLRev/git repository. Run\n    colrev init"
            raise colrev_exceptions.RepoSetupError(msg) from exc

        if not self.review_manager.verbose_mode:
            temp_f = io.StringIO()
            pybtex.io.stderr = temp_f

        self.masterdata_restrictions = self.__get_masterdata_restrictions()
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
            for record_header_item in self.__read_record_header_items(
                file_object=file_object
            ):
                for origin in record_header_item["colrev_origin"]:
                    current_origin_states_dict[origin] = record_header_item[
                        "colrev_status"
                    ]
        return current_origin_states_dict

    def get_committed_origin_state_dict(self) -> dict:
        """Get the committed origin_state_dict"""

        filecontents = self.__get_last_records_filecontents()
        committed_origin_state_dict = self.get_origin_state_dict(
            file_object=io.StringIO(filecontents.decode("utf-8"))
        )
        return committed_origin_state_dict

    def get_nr_in_bib(self, *, file_path: Path) -> int:
        """Returns number of records in the bib file"""
        number_in_bib = 0
        with open(file_path, encoding="utf8") as file:
            line = file.readline()
            while line:
                if "@" in line[:3]:
                    if "@comment" not in line[:10].lower():
                        number_in_bib += 1
                line = file.readline()
        return number_in_bib

    def load_records_from_history(
        self, *, commit_sha: str = ""
    ) -> typing.Iterator[dict]:
        """Returns an iterator of the records_dict based on git history"""

        # If the records are not in the commit (commit_sha), we note that the
        # commit_sha was foud, but that the records were not changed in that commit.
        # It means that we ignore the StopIterations and
        # return the records from the next (prior) commit
        found_but_not_changed = False
        skipped_prior_commits = False  # if no commit_sha provided
        for commit in self.__git_repo.iter_commits():
            if commit_sha:
                if not skipped_prior_commits:
                    if not found_but_not_changed:
                        if commit_sha == commit.hexsha:
                            skipped_prior_commits = True
                        else:
                            continue

            try:
                filecontents = (
                    commit.tree / str(self.RECORDS_FILE_RELATIVE)
                ).data_stream.read()
                # Note : reinitialize parser (otherwise, bib_data does not change)
                parser = bibtex.Parser()
                bib_data = parser.parse_string(filecontents.decode("utf-8"))
                records_dict = self.parse_records_dict(records_dict=bib_data.entries)
            except (StopIteration, KeyError):
                found_but_not_changed = True
                continue
            yield records_dict

    def get_changed_records(self, *, target_commit: str) -> typing.List[dict]:
        """Get the records that changed in a selected commit"""

        revlist = (
            (
                commit.hexsha,
                (commit.tree / str(self.RECORDS_FILE_RELATIVE)).data_stream.read(),
            )
            for commit in self.__git_repo.iter_commits(
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
                if any(x in record["colrev_origin"] for x in rec["colrev_origin"])
            ]
            if not prior_record_l:
                continue
            prior_record = prior_record_l[0]
            # Note: the following is an exact comparison of all fields
            if record != prior_record:
                record.update(changed_in_target_commit="True")

        return list(records_dict.values())

    @classmethod
    def __load_field_dict(cls, *, value: str, field: str) -> dict:
        # pylint: disable=too-many-branches

        return_dict = {}
        if field == "colrev_masterdata_provenance":
            if value[:7] == "CURATED":
                if value.count(";") == 0:
                    value += ";;"  # Note : temporary fix (old format)
                if value.count(";") == 1:
                    value += ";"  # Note : temporary fix (old format)

                if ":" in value:
                    source = value[value.find(":") + 1 : value[:-1].rfind(";")]
                else:
                    source = ""
                return_dict["CURATED"] = {
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
                    if ":" in key_source:
                        note = item[item[:-1].rfind(";") + 1 : -1]
                        key, source = key_source.split(":", 1)
                        # key = key.rstrip().lstrip()
                        return_dict[key] = {
                            "source": source,
                            "note": note,
                        }
                    else:
                        print(f"problem with masterdata_provenance_item {item}")

        elif field == "colrev_data_provenance":
            if value != "":
                # Note : pybtex replaces \n upon load
                for item in (value + " ").split("; "):
                    if item == "":
                        continue
                    item += ";"  # removed by split
                    key_source = item[: item[:-1].rfind(";")]
                    note = item[item[:-1].rfind(";") + 1 : -1]
                    if ":" in key_source:
                        key, source = key_source.split(":", 1)
                        return_dict[key] = {
                            "source": source,
                            "note": note,
                        }
                    else:
                        print(f"problem with data_provenance_item {item}")

        else:
            print(f"error loading dict_field: {field}")

        return return_dict

    @classmethod
    def parse_records_dict(cls, *, records_dict: dict) -> dict:
        """Parse a records_dict from pybtex to colrev standard"""

        def format_name(person: Person) -> str:
            def join(name_list: list) -> str:
                return " ".join([name for name in name_list if name])

            first = person.get_part_as_text("first")
            middle = person.get_part_as_text("middle")
            prelast = person.get_part_as_text("prelast")
            last = person.get_part_as_text("last")
            lineage = person.get_part_as_text("lineage")
            name_string = ""
            if last:
                name_string += join([prelast, last])
            if lineage:
                name_string += f", {lineage}"
            if first or middle:
                name_string += ", "
                name_string += join([first, middle])
            return name_string

        # Need to concatenate fields and persons dicts
        # but pybtex is still the most efficient solution.
        records_dict = {
            k: {
                **{"ID": k},
                **{"ENTRYTYPE": v.type},
                **dict(
                    {
                        # Cast status to Enum
                        k: colrev.record.RecordState[v] if ("colrev_status" == k)
                        # DOIs are case insensitive -> use upper case.
                        else v.upper() if ("doi" == k)
                        # Note : the following two lines are a temporary fix
                        # to converg colrev_origins to list items
                        else [el.rstrip().lstrip() for el in v.split(";") if "" != el]
                        if k == "colrev_origin"
                        else [el.rstrip() for el in (v + " ").split("; ") if "" != el]
                        if k in colrev.record.Record.list_fields_keys
                        else Dataset.__load_field_dict(value=v, field=k)
                        if k in colrev.record.Record.dict_fields_keys
                        else v
                        for k, v in v.fields.items()
                    }
                ),
                **dict(
                    {
                        k: " and ".join(format_name(person) for person in persons)
                        for k, persons in v.persons.items()
                    }
                ),
            }
            for k, v in records_dict.items()
        }

        return records_dict

    def __read_record_header_items(
        self, *, file_object: Optional[typing.TextIO] = None
    ) -> list:
        # Note : more than 10x faster than the pybtex part of load_records_dict()

        # pylint: disable=too-many-statements

        def parse_k_v(current_key_value_pair_str: str) -> tuple:
            try:
                if " = " in current_key_value_pair_str:
                    key, value = current_key_value_pair_str.split(" = ", 1)
                else:
                    key = "ID"
                    value = current_key_value_pair_str.split("{")[1]

                key = key.lstrip().rstrip()
                value = value.lstrip().rstrip().lstrip("{").rstrip("},")
                if key == "colrev_origin":
                    value_list = value.replace("\n", "").split(";")
                    value_list = [x.lstrip(" ").rstrip(" ") for x in value_list if x]
                    return key, value_list
                if key == "colrev_status":
                    return key, colrev.record.RecordState[value]
                if key == "colrev_masterdata_provenance":
                    return key, self.__load_field_dict(value=value, field=key)
                if key == "file":
                    return key, Path(value)
            except IndexError as exc:
                raise colrev_exceptions.BrokenFilesError(
                    msg="parsing records.bib"
                ) from exc

            return key, value

        # pylint: disable=consider-using-with
        if file_object is None:
            file_object = open(self.records_file, encoding="utf-8")

        # Fields required
        default = {
            "ID": "NA",
            "colrev_origin": "NA",
            "colrev_status": "NA",
            "file": "NA",
            "screening_criteria": "NA",
            "colrev_masterdata_provenance": "NA",
        }
        number_required_header_items = len(default)

        record_header_item = default.copy()
        current_header_item_count, current_key_value_pair_str, record_header_items = (
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

            if current_header_item_count > number_required_header_items or "}" == line:
                record_header_items.append(record_header_item)
                record_header_item = default.copy()
                current_header_item_count = 0
                continue

            if "@" in line[:2] and record_header_item["ID"] != "NA":
                record_header_items.append(record_header_item)
                record_header_item = default.copy()
                current_header_item_count = 0

            current_key_value_pair_str += line
            if "}," in line or "@" in line[:2]:
                key, value = parse_k_v(current_key_value_pair_str)
                if key == "colrev_masterdata_provenance":
                    if value == "NA":
                        value = {}
                if value == "NA":
                    current_key_value_pair_str = ""
                    continue
                current_key_value_pair_str = ""
                if key in record_header_item:
                    current_header_item_count += 1
                    record_header_item[key] = value
        if record_header_item["colrev_origin"] != "NA":
            record_header_items.append(record_header_item)
        return [
            {k: v for k, v in record_header_item.items() if "NA" != v}
            for record_header_item in record_header_items
        ]

    def load_records_dict(
        self,
        *,
        file_path: Optional[Path] = None,
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
        'colrev_masterdata_provenance': {"author":{"source":"...", "note":"..."}}},
        }
        """

        if self.review_manager.notified_next_operation is None:
            raise colrev_exceptions.ReviewManagerNotNofiedError()

        pybtex.errors.set_strict_mode(False)
        if header_only:
            # Note : currently not parsing screening_criteria to settings.ScreeningCriterion
            # to optimize performance
            record_header_list = (
                self.__read_record_header_items() if self.records_file.is_file() else []
            )
            record_header_dict = {r["ID"]: r for r in record_header_list}
            return record_header_dict

        if file_path:
            with open(file_path, encoding="utf-8") as file:
                load_str = file.read()

        parser = bibtex.Parser()
        if load_str:
            bib_data = parser.parse_string(load_str)
            records_dict = self.parse_records_dict(records_dict=bib_data.entries)

        elif self.records_file.is_file():
            bib_data = parser.parse_file(str(self.records_file))
            records_dict = self.parse_records_dict(records_dict=bib_data.entries)
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
        language_service = colrev.env.language_service.LanguageService()
        first = True
        for record_id, record_dict in recs_dict.items():
            if not first:
                bibtex_str += "\n"
            first = False

            bibtex_str += f"@{record_dict['ENTRYTYPE']}{{{record_id}"

            try:
                language_service.unify_to_iso_639_3_language_codes(
                    record=colrev.record.Record(data=record_dict)
                )
            except colrev_exceptions.InvalidLanguageCodeException:
                del record_dict["language"]

            field_order = [
                "colrev_origin",  # must be in second line
                "colrev_status",
                "colrev_masterdata_provenance",
                "colrev_data_provenance",
                "colrev_pdf_id",
                "screening_criteria",
                "file",  # Note : do not change this order (parsers rely on it)
                "prescreen_exclusion",
                "doi",
                "grobid-version",
                "dblp_key",
                "sem_scholar_id",
                "wos_accession_number",
                "author",
                "booktitle",
                "journal",
                "title",
                "year",
                "volume",
                "number",
                "pages",
                "editor",
            ]

            record = colrev.record.Record(data=record_dict)
            record_dict = record.get_data(stringify=True)

            for ordered_field in field_order:
                if ordered_field in record_dict:
                    if record_dict[ordered_field] == "":
                        continue
                    bibtex_str += format_field(
                        ordered_field, record_dict[ordered_field]
                    )

            for key, value in record_dict.items():
                if key in field_order + ["ID", "ENTRYTYPE"]:
                    continue

                bibtex_str += format_field(key, value)

            bibtex_str += ",\n}\n"

        return bibtex_str

    def save_records_dict_to_file(self, *, records: dict, save_path: Path) -> None:
        """Save the records dict to specifified file"""
        # Note : this classmethod function can be called by CoLRev scripts
        # operating outside a CoLRev repo (e.g., sync)

        bibtex_str = self.parse_bibtex_str(recs_dict_in=records)

        with open(save_path, "w", encoding="utf-8") as out:
            out.write(bibtex_str + "\n")

    def __save_record_list_by_id(
        self, *, records: dict, append_new: bool = False
    ) -> None:
        # Note : currently no use case for append_new=True??

        parsed = self.parse_bibtex_str(recs_dict_in=records)
        record_list = [
            {
                "ID": item[item.find("{") + 1 : item.find(",")],
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
                    if current_id_str in [x["ID"] for x in record_list]:
                        replacement = [x["record"] for x in record_list][0]
                        record_list = [
                            x for x in record_list if x["ID"] != current_id_str
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
                    "records not written to file: " f'{[x["ID"] for x in record_list]}'
                )

        self.add_record_changes()

    def save_records_dict(self, *, records: dict, partial: bool = False) -> None:
        """Save the records dict in RECORDS_FILE"""

        if partial:
            self.__save_record_list_by_id(records=records)
            return
        self.save_records_dict_to_file(records=records, save_path=self.records_file)

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

    def format_records_file(self) -> bool:
        """Format the records file"""

        records = self.load_records_dict()
        for record_dict in records.values():
            if "colrev_status" not in record_dict:
                print(f'Error: no status field in record ({record_dict["ID"]})')
                continue

            record = colrev.record.PrepRecord(data=record_dict)
            if record_dict["colrev_status"] in [
                colrev.record.RecordState.md_needs_manual_preparation,
            ]:
                record.update_masterdata_provenance(
                    masterdata_restrictions=self.get_applicable_restrictions(
                        record_dict=record_dict
                    )
                )
                record.update_metadata_status()

            if record_dict["colrev_status"] == colrev.record.RecordState.pdf_prepared:
                record.reset_pdf_provenance_notes()

        self.save_records_dict(records=records)
        changed = self.RECORDS_FILE_RELATIVE in [
            r.a_path for r in self.__git_repo.index.diff(None)
        ]
        return changed

    # ID creation, update and lookup ---------------------------------------

    def reprocess_id(self, *, paper_ids: str) -> None:
        """Remove an ID (set of IDs) from the bib_db (for reprocessing)"""

        saved_args = locals()
        if paper_ids == "all":
            # self.review_manager.logger.info("Removing/reprocessing all records")
            os.remove(self.records_file)
            self.__git_repo.index.remove(
                [str(self.RECORDS_FILE_RELATIVE)],
                working_tree=True,
            )
        else:
            records = self.load_records_dict()
            records = {
                ID: record
                for ID, record in records.items()
                if ID not in paper_ids.split(",")
            }
            self.save_records_dict(records=records)
            self.add_record_changes()

        self.review_manager.create_commit(msg="Reprocess", saved_args=saved_args)

    def __generate_temp_id(
        self, *, local_index: colrev.env.local_index.LocalIndex, record_dict: dict
    ) -> str:
        # pylint: disable=too-many-branches

        try:
            retrieved_record = local_index.retrieve(record_dict=record_dict)
            temp_id = retrieved_record["ID"]

            # Do not use IDs from local_index for curated_metadata repositories
            if "curated_metadata" in str(self.review_manager.path):
                raise colrev_exceptions.RecordNotInIndexException()

        except (
            colrev_exceptions.RecordNotInIndexException,
            colrev_exceptions.NotEnoughDataToIdentifyException,
        ):
            if record_dict.get("author", record_dict.get("editor", "")) != "":
                authors_string = record_dict.get(
                    "author", record_dict.get("editor", "Anonymous")
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
                temp_id = (
                    f'{author.replace(" ", "")}{str(record_dict.get("year", "NoYear"))}'
                )
            elif colrev.settings.IDPattern.three_authors_year == id_pattern:
                temp_id = ""
                indices = len(authors)
                if len(authors) > 3:
                    indices = 3
                for ind in range(0, indices):
                    temp_id = temp_id + f'{authors[ind].split(",")[0].replace(" ", "")}'
                if len(authors) > 3:
                    temp_id = temp_id + "EtAl"
                temp_id = temp_id + str(record_dict.get("year", "NoYear"))

            if temp_id.isupper():
                temp_id = temp_id.capitalize()
            # Replace special characters
            # (because IDs may be used as file names)
            temp_id = colrev.env.utils.remove_accents(input_str=temp_id)
            temp_id = re.sub(r"\(.*\)", "", temp_id)
            temp_id = re.sub("[^0-9a-zA-Z]+", "", temp_id)

        return temp_id

    def generate_next_unique_id(
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
            if record["ID"] == record_id:
                if record[
                    "colrev_status"
                ] in colrev.record.RecordState.get_post_x_states(
                    state=colrev.record.RecordState.md_processed
                ):
                    return True

        return False

    def __generate_id(
        self,
        *,
        local_index: colrev.env.local_index.LocalIndex,
        record_dict: dict,
        existing_ids: Optional[list] = None,
    ) -> str:
        """Generate a blacklist to avoid setting duplicate IDs"""

        # Only change IDs that are before md_processed
        if record_dict["colrev_status"] in colrev.record.RecordState.get_post_x_states(
            state=colrev.record.RecordState.md_processed
        ):
            raise colrev_exceptions.PropagatedIDChange([record_dict["ID"]])
        # Alternatively, we could change IDs except for those
        # that have been propagated to the
        # screen or data will not be replaced
        # (this would break the chain of evidence)

        temp_id = self.__generate_temp_id(
            local_index=local_index, record_dict=record_dict
        )

        if existing_ids:
            temp_id = self.generate_next_unique_id(
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
            record_dict = records[record_id]
            if selected_ids is not None:
                if record_id not in selected_ids:
                    continue
            if (
                record_dict["colrev_status"]
                not in [
                    colrev.record.RecordState.md_imported,
                    colrev.record.RecordState.md_prepared,
                ]
                and not self.review_manager.force_mode
            ):
                continue
            old_id = record_id

            temp_stat = record_dict["colrev_status"]
            if selected_ids:
                record = colrev.record.Record(data=record_dict)
                record.set_status(target_state=colrev.record.RecordState.md_prepared)
            new_id = self.__generate_id(
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
                self.review_manager.report_logger.info(f"set_ids({old_id}) to {new_id}")
                if old_id in id_list:
                    id_list.remove(old_id)

        self.save_records_dict(records=records)
        self.add_record_changes()

        return records

    def get_next_id(self, *, bib_file: Path) -> int:
        """Get the next ID (incrementing counter)"""
        ids = []
        if bib_file.is_file():
            with open(bib_file, encoding="utf8") as file:
                line = file.readline()
                while line:
                    if "@" in line[:3]:
                        current_id = line[line.find("{") + 1 : line.rfind(",")]
                        ids.append(current_id)
                    line = file.readline()
        max_id = max([int(cid) for cid in ids if cid.isdigit()] + [0]) + 1
        return max_id

    def __get_masterdata_restrictions(self) -> dict:
        masterdata_restrictions = {}
        curated_endpoints = [
            x
            for x in self.review_manager.settings.data.data_package_endpoints
            if x["endpoint"] == "colrev.colrev_curation"
        ]
        if curated_endpoints:
            curated_endpoint = curated_endpoints[0]
            masterdata_restrictions = curated_endpoint.get(
                "masterdata_restrictions", {}
            )
        return masterdata_restrictions

    def get_applicable_restrictions(self, *, record_dict: dict) -> dict:
        """Get the applicable masterdata restrictions"""

        applicable_restrictions = {}

        start_year_values = list(self.masterdata_restrictions.keys())

        if not str(record_dict.get("year", "NA")).isdigit():
            return {}

        year_index_diffs = [
            int(record_dict["year"]) - int(x) for x in start_year_values
        ]
        year_index_diffs = [x if x >= 0 else 2000 for x in year_index_diffs]

        if not year_index_diffs:
            return {}

        index_min = min(range(len(year_index_diffs)), key=year_index_diffs.__getitem__)
        applicable_restrictions = self.masterdata_restrictions[
            start_year_values[index_min]
        ]

        return applicable_restrictions

    # GIT operations -----------------------------------------------

    def get_repo(self) -> git.Repo:
        """Get the git repository object (requires review_manager.notify(...))"""

        if self.review_manager.notified_next_operation is None:
            raise colrev_exceptions.ReviewManagerNotNofiedError()
        return self.__git_repo

    def has_changes(
        self, *, relative_path: Optional[Path] = None, change_type: str = "all"
    ) -> bool:
        """Check whether the relative path (or the git repository) has changes"""

        if relative_path:
            main_recs_changed = False
            try:
                if change_type == "all":
                    main_recs_changed = str(relative_path) in [
                        item.a_path for item in self.__git_repo.index.diff(None)
                    ] + [item.a_path for item in self.__git_repo.head.commit.diff()]
                elif change_type == "staged":
                    main_recs_changed = str(relative_path) in [
                        item.a_path for item in self.__git_repo.head.commit.diff()
                    ]

                elif change_type == "unstaged":
                    main_recs_changed = str(relative_path) in [
                        item.a_path for item in self.__git_repo.index.diff(None)
                    ]
            except ValueError:
                pass
            return main_recs_changed

        return self.__git_repo.is_dirty()

    def add_changes(self, *, path: Path, remove: bool = False) -> None:
        """Add changed file to git"""

        if path.is_absolute():
            path = path.relative_to(self.review_manager.path)

        while (self.review_manager.path / Path(".git/index.lock")).is_file():
            time.sleep(0.5)
            print("Waiting for previous git operation to complete")

        try:
            if remove:
                self.__git_repo.index.remove([str(path)])
            else:
                self.__git_repo.index.add([str(path)])
        except GitCommandError:
            pass

    def get_untracked_files(self) -> list:
        """Get the files that are untracked by git"""

        return self.__git_repo.untracked_files

    def __get_last_records_filecontents(self) -> bytes:
        revlist = (
            (
                commit.hexsha,
                (commit.tree / str(self.RECORDS_FILE_RELATIVE)).data_stream.read(),
            )
            for commit in self.__git_repo.iter_commits(
                paths=str(self.RECORDS_FILE_RELATIVE)
            )
        )
        filecontents = list(revlist)[0][1]
        return filecontents

    def records_changed(self) -> bool:
        """Check whether the records were changed"""
        try:
            main_recs_changed = str(self.RECORDS_FILE_RELATIVE) in [
                item.a_path for item in self.__git_repo.index.diff(None)
            ] + [x.a_path for x in self.__git_repo.head.commit.diff()]
            self.__get_last_records_filecontents()
        except (IndexError, ValueError, KeyError):
            main_recs_changed = False
        return main_recs_changed

    def remove_file_from_git(self, *, path: str) -> None:
        """Remove a file from git"""
        self.__git_repo.index.remove([path], working_tree=True)

    def create_commit(
        self, *, msg: str, author: git.Actor, committer: git.Actor, hook_skipping: bool
    ) -> None:
        """Create a commit"""
        self.__git_repo.index.commit(
            msg,
            author=author,
            committer=committer,
            skip_hooks=hook_skipping,
        )

    def file_in_history(self, *, filepath: Path) -> bool:
        """Check whether a file is in the git history"""
        return str(filepath) in [
            o.path for o in self.__git_repo.head.commit.tree.traverse()
        ]

    def get_commit_message(self, *, commit_nr: int) -> str:
        """Get the commit message for commit #"""
        master = self.__git_repo.head.reference
        assert commit_nr == 0  # extension : implement other cases
        if commit_nr == 0:
            cmsg = master.commit.message
        return cmsg

    def add_record_changes(self) -> None:
        """Add changes in records to git"""
        while (self.review_manager.path / Path(".git/index.lock")).is_file():
            time.sleep(0.5)
            print("Waiting for previous git operation to complete")
        self.__git_repo.index.add([str(self.RECORDS_FILE_RELATIVE)])

    def add_setting_changes(self) -> None:
        """Add changes in settings to git"""
        while (self.review_manager.path / Path(".git/index.lock")).is_file():
            time.sleep(0.5)
            print("Waiting for previous git operation to complete")

        self.__git_repo.index.add([str(self.review_manager.SETTINGS_RELATIVE)])

    def has_untracked_search_records(self) -> bool:
        """Check whether there are untracked search records"""
        search_dir = str(self.review_manager.SEARCHDIR_RELATIVE) + "/"
        untracked_files = self.get_untracked_files()
        return any(search_dir in untracked_file for untracked_file in untracked_files)

    def reset_log_if_no_changes(self) -> None:
        """Reset the report log file if there are not changes"""
        if not self.__git_repo.is_dirty():
            self.review_manager.reset_report_logger()

    def get_last_commit_sha(self) -> str:  # pragma: no cover
        """Get the last commit sha"""
        return str(self.__git_repo.head.commit.hexsha)

    def get_tree_hash(self) -> str:  # pragma: no cover
        """Get the current tree hash"""
        tree_hash = self.__git_repo.git.execute(["git", "write-tree"])
        return str(tree_hash)

    def __get_remote_commit_differences(self) -> list:  # pragma: no cover
        origin = self.__git_repo.remotes.origin
        if origin.exists():
            try:
                origin.fetch()
            except GitCommandError:
                return [-1, -1]

        nr_commits_behind, nr_commits_ahead = -1, -1
        if self.__git_repo.active_branch.tracking_branch() is not None:
            branch_name = str(self.__git_repo.active_branch)
            tracking_branch_name = str(self.__git_repo.active_branch.tracking_branch())
            # self.review_manager.logger.debug(f"{branch_name} - {tracking_branch_name}")

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = self.__git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = self.__git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

        return [nr_commits_behind, nr_commits_ahead]

    def behind_remote(self) -> bool:  # pragma: no cover
        """Check whether the repository is behind the remote"""
        nr_commits_behind = 0
        connected_remote = 0 != len(self.__git_repo.remotes)
        if connected_remote:
            origin = self.__git_repo.remotes.origin
            if origin.exists():
                (
                    nr_commits_behind,
                    _,
                ) = self.__get_remote_commit_differences()
        if nr_commits_behind > 0:
            return True
        return False

    def remote_ahead(self) -> bool:  # pragma: no cover
        """Check whether the remote is ahead"""
        connected_remote = 0 != len(self.__git_repo.remotes)
        if connected_remote:
            origin = self.__git_repo.remotes.origin
            if origin.exists():
                (
                    _,
                    nr_commits_ahead,
                ) = self.__get_remote_commit_differences()
        if nr_commits_ahead > 0:
            return True
        return False

    def pull_if_repo_clean(self) -> None:  # pragma: no cover
        """Pull project if repository is clean"""
        if not self.__git_repo.is_dirty():
            origin = self.__git_repo.remotes.origin
            origin.pull()

    def get_remote_url(self) -> str:  # pragma: no cover
        """Get the remote url"""
        remote_url = "NA"
        for remote in self.__git_repo.remotes:
            if remote.name == "origin":
                remote_url = remote.url
        return remote_url


if __name__ == "__main__":
    pass
