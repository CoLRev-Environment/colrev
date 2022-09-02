#!/usr/bin/env python3
from __future__ import annotations

import io
import itertools
import json
import logging
import os
import re
import shutil
import string
import time
import typing
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

import git
import pandas as pd
import pybtex.errors
from dictdiffer import diff
from git.exc import GitCommandError
from git.exc import InvalidGitRepositoryError
from pybtex.database.input import bibtex
from tqdm import tqdm

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record
import colrev.settings

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager


class Dataset:
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:

        self.review_manager = review_manager
        self.records_file = review_manager.paths["RECORDS_FILE"]
        try:
            self.__git_repo = git.Repo(self.review_manager.path)
        except InvalidGitRepositoryError as exc:
            msg = "Not a CoLRev/git repository. Run\n    colrev init"
            raise colrev_exceptions.RepoSetupError(msg) from exc

    def get_record_state_list(self) -> list:
        """Get the record_state_list"""

        if not self.records_file.is_file():
            record_state_list = []
        else:
            record_state_list = self.__read_record_header_items()
        return record_state_list

    def get_origin_state_dict(self, *, file_object=None) -> dict:
        ret_dict = {}
        if self.records_file.is_file():
            for record_header_item in self.__read_record_header_items(
                file_object=file_object
            ):
                for origin in record_header_item["colrev_origin"].split(";"):
                    ret_dict[origin] = record_header_item["colrev_status"]

        return ret_dict

    def get_record_header_list(self) -> list:
        """Get the record_header_list"""

        if not self.records_file.is_file():
            return []
        return self.__read_record_header_items()

    def get_currently_imported_origin_list(self) -> list:
        record_header_list = self.review_manager.dataset.get_record_header_list()
        imported_origins = [x["colrev_origin"].split(";") for x in record_header_list]
        imported_origins = list(itertools.chain(*imported_origins))
        return imported_origins

    def get_states_set(self, *, record_state_list: list = None) -> set:
        """Get the record_states_set"""

        if not self.records_file.is_file():
            return set()
        if record_state_list is None:
            record_state_list = self.get_record_state_list()
        return {el["colrev_status"] for el in record_state_list}

    def get_nr_in_bib(self, *, file_path: Path) -> int:
        number_in_bib = 0
        with open(file_path, encoding="utf8") as file:
            line = file.readline()
            while line:
                # Note: the '﻿' occured in some bibtex files
                # (e.g., Publish or Perish exports)
                if "@" in line[:3]:
                    if "@comment" not in line[:10].lower():
                        number_in_bib += 1
                line = file.readline()
        return number_in_bib

    def retrieve_records_from_history(
        self,
        *,
        original_records: list[dict],
        condition_state: colrev.record.RecordState,
    ) -> list:

        prior_records = []
        records_file_relative = self.review_manager.paths["RECORDS_FILE_RELATIVE"]
        git_repo = self.__git_repo
        revlist = (
            (
                commit.hexsha,
                commit.message,
                (commit.tree / str(records_file_relative)).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(records_file_relative))
        )

        retrieved = []
        for _, _, filecontents in list(revlist):
            prior_records_dict = self.load_records_dict(
                load_str=filecontents.decode("utf-8")
            )
            for prior_record in prior_records_dict.values():
                if str(prior_record.get("colrev_status", "NA")) != str(condition_state):
                    continue
                for original_record in original_records:

                    if any(
                        o in prior_record["colrev_origin"]
                        for o in original_record["colrev_origin"].split(";")
                    ):
                        prior_records.append(prior_record)
                        # only take the latest version (i.e., drop the record)
                        # Note: only append the first one if origins were in
                        # different records (after deduplication)
                        retrieved.append(original_record["ID"])
                original_records = [
                    orec for orec in original_records if orec["ID"] not in retrieved
                ]

        return prior_records

    @classmethod
    def load_field_dict(cls, *, value: str, field: str) -> dict:
        return_dict = {}
        if "colrev_masterdata_provenance" == field:
            if "CURATED" == value[:7]:
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

            elif "" != value:
                # TODO : discuss: "; " as an indicator for the next list
                # item is not ideal (could easily be part of a field value....)
                for item in (value + " ").split("; "):
                    if "" == item:
                        continue
                    item += ";"  # removed by split
                    key_source = item[: item[:-1].rfind(";")]
                    if ":" in key_source:
                        note = item[item[:-1].rfind(";") + 1 : -1]
                        key, source = key_source.split(":", 1)
                        return_dict[key] = {
                            "source": source,
                            "note": note,
                        }
                    else:
                        print(f"problem with masterdata_provenance_item {item}")

        elif "colrev_data_provenance" == field:
            if "" != value:
                # Note : pybtex replaces \n upon load
                for item in (value + " ").split("; "):
                    if "" == item:
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
            print(f"error loading dict_field: {key}")

        return return_dict

    @classmethod
    def parse_records_dict(cls, *, records_dict: dict) -> dict:
        def format_name(person):
            def join(name_list):
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
                        # DOIs are case sensitive -> use upper case.
                        else v.upper()
                        if ("doi" == k)
                        else [el.rstrip() for el in (v + " ").split("; ") if "" != el]
                        if k in colrev.record.Record.list_fields_keys
                        else Dataset.load_field_dict(value=v, field=k)
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

    def load_records_dict(self, *, load_str: str = None) -> dict:
        """Get the records (requires review_manager.notify(...))"""

        # TODO : optional dict-key as a parameter

        pybtex.errors.set_strict_mode(False)

        if self.review_manager.notified_next_process is None:
            raise colrev_exceptions.ReviewManagerNotNofiedError()

        parser = bibtex.Parser()

        if load_str:
            bib_data = parser.parse_string(load_str)
            records_dict = self.parse_records_dict(records_dict=bib_data.entries)

        elif self.records_file.is_file():
            bib_data = parser.parse_file(self.records_file)
            records_dict = self.parse_records_dict(records_dict=bib_data.entries)
        else:
            records_dict = {}

        return records_dict

    def load_origin_records(self) -> dict:

        origin_records: dict[str, typing.Any] = {}
        sources = [x.filename for x in self.review_manager.settings.sources]
        for source in sources:
            source_file = self.review_manager.paths["SEARCHDIR_RELATIVE"] / Path(source)
            if source_file.is_file():
                with open(source_file, encoding="utf8") as target_db:

                    source_record_dict = self.load_records_dict(
                        load_str=target_db.read()
                    )

                    records_dict = {
                        f"{source}/{r['ID']}": {r.items()}
                        for r in source_record_dict.values()
                    }
                    origin_records = {**origin_records, **records_dict}

        return origin_records

    def load_from_git_history(self):
        records_file_relative = self.review_manager.paths["RECORDS_FILE_RELATIVE"]
        git_repo = self.review_manager.dataset.get_repo()
        revlist = (
            (
                commit.hexsha,
                commit.message,
                (commit.tree / str(records_file_relative)).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(records_file_relative))
        )

        for _, _, filecontents in list(revlist):
            prior_records_dict = self.load_records_dict(load_str=filecontents)

            records_dict = {
                r["ID"]: {
                    k: colrev.record.RecordState[v]
                    if ("colrev_status" == k)
                    else v.upper()
                    if ("doi" == k)
                    else v
                    for k, v in r.items()
                }
                for r in prior_records_dict.values()
            }
            yield records_dict

    @classmethod
    def parse_bibtex_str(cls, *, recs_dict_in: dict) -> str:

        # Note: we need a deepcopy because the parsing modifies dicts
        recs_dict = deepcopy(recs_dict_in)

        def format_field(field, value) -> str:
            padd = " " * max(0, 28 - len(field))
            return f",\n   {field} {padd} = {{{value}}}"

        bibtex_str = ""

        first = True
        for record_id, record_dict in recs_dict.items():
            if not first:
                bibtex_str += "\n"
            first = False

            bibtex_str += f"@{record_dict['ENTRYTYPE']}{{{record_id}"

            field_order = [
                "colrev_origin",  # must be in second line
                "colrev_status",  # must be in third line
                "colrev_masterdata_provenance",
                "colrev_data_provenance",
                "colrev_id",
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
                    if "" == record_dict[ordered_field]:
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

    @classmethod
    def save_records_dict_to_file(cls, *, records: dict, save_path: Path) -> None:
        """Save the records dict to specifified file"""
        # Note : this classmethod function can be called by CoLRev scripts
        # operating outside a CoLRev repo (e.g., sync)

        bibtex_str = Dataset.parse_bibtex_str(recs_dict_in=records)

        with open(save_path, "w", encoding="utf-8") as out:
            out.write(bibtex_str)

        # TBD: the caseing may not be necessary
        # because we create a new list of dicts when casting to strings...
        # # Casting to RecordState (in case the records are used afterwards)
        # records = [
        #     {k: RecordState[v] if ("colrev_status" == k) else v for k, v in r.items()}
        #     for r in records
        # ]

        # # DOIs are case sensitive -> use upper case.
        # records = [
        #     {k: v.upper() if ("doi" == k) else v for k, v in r.items()}
        #      for r in records
        # ]

    def save_records_dict(self, *, records: dict) -> None:
        """Save the records dict in RECORDS_FILE"""

        self.save_records_dict_to_file(records=records, save_path=self.records_file)

    def reprocess_id(self, *, paper_ids: str) -> None:
        """Remove an ID (set of IDs) from the bib_db (for reprocessing)"""

        saved_args = locals()

        if "all" == paper_ids:
            # logging.info("Removing/reprocessing all records")
            os.remove(self.records_file)
            self.__git_repo.index.remove(
                [str(self.review_manager.paths["RECORDS_FILE_RELATIVE"])],
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

    def set_ids(self, *, records: dict = None, selected_ids: list = None) -> dict:
        """Set the IDs of records according to predefined formats or
        according to the LocalIndex"""
        # pylint: disable=redefined-outer-name

        local_index = self.review_manager.get_local_index()

        def generate_id_blacklist(
            *,
            record_dict: dict,
            id_blacklist: list = None,
            record_in_bib_db: bool = False,
            raise_error: bool = True,
        ) -> str:
            """Generate a blacklist to avoid setting duplicate IDs"""

            # Make sure that IDs that have been propagated to the
            # screen or data will not be replaced
            # (this would break the chain of evidence)
            if raise_error:
                if self.propagated_id(record_id=record_dict["ID"]):
                    raise colrev_exceptions.PropagatedIDChange([record_dict["ID"]])
            try:
                retrieved_record = local_index.retrieve(record_dict=record_dict)
                temp_id = retrieved_record["ID"]
            except colrev_exceptions.RecordNotInIndexException:

                if "" != record_dict.get("author", record_dict.get("editor", "")):
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
                    temp_id = f'{author.replace(" ", "")}{str(record_dict.get("year", "NoYear"))}'

                if colrev.settings.IDPattern.three_authors_year == id_pattern:
                    temp_id = ""
                    indices = len(authors)
                    if len(authors) > 3:
                        indices = 3
                    for ind in range(0, indices):
                        temp_id = (
                            temp_id + f'{authors[ind].split(",")[0].replace(" ", "")}'
                        )
                    if len(authors) > 3:
                        temp_id = temp_id + "EtAl"
                    temp_id = temp_id + str(record_dict.get("year", "NoYear"))

                if temp_id.isupper():
                    temp_id = temp_id.capitalize()
                # Replace special characters
                # (because IDs may be used as file names)
                temp_id = colrev.record.Record.remove_accents(input_str=temp_id)
                temp_id = re.sub(r"\(.*\)", "", temp_id)
                temp_id = re.sub("[^0-9a-zA-Z]+", "", temp_id)

            if id_blacklist is not None:
                if record_in_bib_db:
                    # allow IDs to remain the same.
                    other_ids = id_blacklist
                    # Note: only remove it once. It needs to change when there are
                    # other records with the same ID
                    if record_dict["ID"] in other_ids:
                        other_ids.remove(record_dict["ID"])
                else:
                    # ID can remain the same, but it has to change
                    # if it is already in bib_db
                    other_ids = id_blacklist

                order = 0
                letters = list(string.ascii_lowercase)
                next_unique_id = temp_id
                appends: list = []
                while next_unique_id.lower() in [i.lower() for i in other_ids]:
                    if len(appends) == 0:
                        order += 1
                        appends = list(itertools.product(letters, repeat=order))
                    next_unique_id = temp_id + "".join(list(appends.pop(0)))
                temp_id = next_unique_id

            return temp_id

        if records is None:
            records = {}

        if len(records) == 0:
            records = self.load_records_dict()

        id_list = list(records.keys())

        for record_id in list(records.keys()):
            record_dict = records[record_id]
            record = colrev.record.Record(data=record_dict)
            if record.masterdata_is_curated():
                continue
            self.review_manager.logger.debug(f"Set ID for {record_id}")
            if selected_ids is not None:
                if record_id not in selected_ids:
                    continue
            elif str(record_dict["colrev_status"]) not in [
                str(colrev.record.RecordState.md_imported),
                str(colrev.record.RecordState.md_prepared),
            ]:
                continue

            old_id = record_id
            new_id = generate_id_blacklist(
                record_dict=record_dict,
                id_blacklist=id_list,
                record_in_bib_db=True,
                raise_error=False,
            )

            id_list.append(new_id)
            if old_id != new_id:
                # We need to insert the a new element into records
                # to make sure that the IDs are actually saved
                record_dict.update(ID=new_id)
                records[new_id] = record_dict
                del records[old_id]
                self.review_manager.report_logger.info(f"set_ID({old_id}) to {new_id}")
                if old_id in id_list:
                    id_list.remove(old_id)

        self.save_records_dict(records=records)
        # Note : temporary fix
        # (to prevent failing format checks caused by special characters)

        # records = self.load_records_dict()
        # self.save_records_dict(records=records)
        self.add_record_changes()

        return records

    def propagated_id(self, *, record_id: str) -> bool:
        """Check whether an ID has been propagated"""

        propagated = False

        if self.review_manager.paths["DATA"].is_file():
            # Note: this may be redundant, but just to be sure:
            data = pd.read_csv(self.review_manager.paths["DATA"], dtype=str)
            if record_id in data["ID"].tolist():
                propagated = True

        # TODO : also check data_pages?

        return propagated

    def __read_record_header_items(self, *, file_object=None) -> list:

        # Note : more than 10x faster than load_records_dict()

        def parse_k_v(current_key_value_pair_str):
            if " = " in current_key_value_pair_str:
                key, value = current_key_value_pair_str.split(" = ", 1)
            else:
                key = "ID"
                value = current_key_value_pair_str.split("{")[1]

            key = key.lstrip().rstrip()
            value = value.lstrip().rstrip().lstrip("{").rstrip("},")
            return key, value

        record_header_items = []
        # pylint: disable=consider-using-with
        if file_object is None:
            file_object = open(self.records_file, encoding="utf-8")

        # Fields required
        default = {
            "ID": "NA",
            "colrev_origin": "NA",
            "colrev_status": "NA",
            "screening_criteria": "NA",
            "file": "NA",
            "colrev_masterdata_provenance": "NA",
        }
        number_required_header_items = len(default)

        record_header_item = default.copy()
        current_header_item_count = 0
        current_key_value_pair_str = ""
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

            if "@" in line[:2] and not "NA" == record_header_item["ID"]:
                record_header_items.append(record_header_item)
                record_header_item = default.copy()
                current_header_item_count = 0

            current_key_value_pair_str += line
            if "}," in line or "@" in line[:2]:
                key, value = parse_k_v(current_key_value_pair_str)
                current_key_value_pair_str = ""
                if key in record_header_item:
                    current_header_item_count += 1
                    record_header_item[key] = value

        record_header_items.append(record_header_item)
        return record_header_items

    def __read_next_record_str(self, *, file_object=None) -> typing.Iterator[str]:
        def yield_from_file(file):
            data = ""
            first_entry_processed = False
            while True:
                line = file.readline()
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

        if file_object is not None:
            yield from yield_from_file(file_object)
        else:
            with open(self.records_file, encoding="utf8") as records_file_object:
                yield from yield_from_file(records_file_object)

    def read_next_record(self, *, conditions: list = None) -> typing.Iterator[dict]:
        # Note : matches conditions connected with 'OR'
        records = []
        record_dict = self.load_records_dict()

        for _, record in record_dict.items():
            if conditions is not None:
                for condition in conditions:
                    for key, value in condition.items():
                        if str(value) == str(record[key]):
                            records.append(record)
            else:
                records.append(record)
        yield from records

    def get_crossref_record(self, *, record_dict: dict) -> dict:
        # Note : the ID of the crossrefed record_dict may have changed.
        # we need to trace based on the colrev_origin
        crossref_origin = record_dict["colrev_origin"]
        crossref_origin = crossref_origin[: crossref_origin.rfind("/")]
        crossref_origin = crossref_origin + "/" + record_dict["crossref"]
        for record_string in self.__read_next_record_str():
            if crossref_origin in record_string:
                records_dict = self.load_records_dict(load_str=record_string)
                record_dict = list(records_dict.values())[0]
                if record_dict["colrev_origin"] == crossref_origin:
                    return record_dict
        return {}

    def replace_field(self, *, ids: list, key: str, val_str: str) -> None:

        val = val_str.encode("utf-8")
        current_id_str = "NA"
        with open(self.records_file, "r+b") as file:
            seekpos = file.tell()
            line = file.readline()
            while line:
                if b"@" in line[:3]:
                    current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                    current_id_str = current_id.decode("utf-8")

                replacement = None
                if current_id_str in ids:
                    if line.lstrip()[: len(key)].decode("utf-8") == key:
                        replacement = line[: line.find(b"{") + 1] + val + b"},\n"

                if replacement:
                    if len(replacement) == len(line):
                        file.seek(seekpos)
                        file.write(replacement)
                        file.flush()
                        os.fsync(file)
                    else:
                        remaining = file.read()
                        file.seek(seekpos)
                        file.write(replacement)
                        seekpos = file.tell()
                        file.flush()
                        os.fsync(file)
                        file.write(remaining)
                        file.truncate()  # if the replacement is shorter...
                        file.seek(seekpos)
                        line = file.readline()
                    ids.remove(current_id_str)
                    if 0 == len(ids):
                        return
                seekpos = file.tell()
                line = file.readline()

    def update_record_by_id(self, *, new_record: dict, delete: bool = False) -> None:

        new_record_dict = {new_record["ID"]: new_record}
        replacement = Dataset.parse_bibtex_str(recs_dict_in=new_record_dict)

        current_id_str = "NA"
        with open(self.records_file, "r+b") as file:
            seekpos = file.tell()
            line = file.readline()
            while line:
                if b"@" in line[:3]:
                    current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                    current_id_str = current_id.decode("utf-8")

                if current_id_str == new_record["ID"]:
                    line = file.readline()
                    while (
                        b"@" not in line[:3] and line
                    ):  # replace: drop the current record
                        line = file.readline()
                    remaining = line + file.read()
                    file.seek(seekpos)
                    if not delete:
                        file.write(replacement.encode("utf-8"))
                        file.write(b"\n")
                    seekpos = file.tell()
                    file.flush()
                    os.fsync(file)
                    file.write(remaining)
                    file.truncate()  # if the replacement is shorter...
                    file.seek(seekpos)
                    line = file.readline()
                    return

                seekpos = file.tell()
                line = file.readline()

    def save_record_list_by_id(
        self, *, record_list: list, append_new: bool = False
    ) -> None:

        if record_list == []:
            return

        record_dict = {r["ID"]: r for r in record_list}
        parsed = Dataset.parse_bibtex_str(recs_dict_in=record_dict)

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
                    for replacement in record_list:
                        m_refs.write(replacement["record"])

            else:
                self.review_manager.report_logger.error(
                    "records not written to file: " f'{[x["ID"] for x in record_list]}'
                )

        self.add_record_changes()

    def format_records_file(self) -> bool:

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
                    unprepared_record=record, review_manager=self.review_manager
                )
                record.update_metadata_status(review_manager=self.review_manager)

            if record_dict["colrev_status"] == colrev.record.RecordState.pdf_prepared:
                record.reset_pdf_provenance_notes()

            # record = RECORD.get_data()

        self.save_records_dict(records=records)
        changed = self.review_manager.paths["RECORDS_FILE_RELATIVE"] in [
            r.a_path for r in self.__git_repo.index.diff(None)
        ]
        return changed

    def retrieve_status_data(self, *, prior: dict) -> dict:

        status_data: dict = {
            "pdf_not_exists": [],
            "status_fields": [],
            "status_transitions": [],
            "start_states": [],
            "screening_criteria_list": [],
            "IDs": [],
            "entries_without_origin": [],
            "record_links_in_bib": [],
            "persisted_IDs": [],
            "origin_list": [],
            "invalid_state_transitions": [],
        }

        with open(self.records_file, encoding="utf8") as file:
            for record_string in self.__read_next_record_str(file_object=file):
                record_id, file_path, status, excl_crit, origin = (
                    "NA",
                    "NA",
                    "NA",
                    "not_set",
                    "NA",
                )

                for line in record_string.split("\n"):
                    if "@Comment" in line:
                        record_id = "Comment"
                        break
                    if "@" in line[:3]:
                        record_id = line[line.find("{") + 1 : line.rfind(",")]
                    if "file" == line.lstrip()[:4]:
                        file_path = line[line.find("{") + 1 : line.rfind("}")]
                    if "colrev_status" == line.lstrip()[:13]:
                        status = line[line.find("{") + 1 : line.rfind("}")]
                    if "screening_criteria" == line.lstrip()[:18]:
                        excl_crit = line[line.find("{") + 1 : line.rfind("}")]
                    if "colrev_origin" == line.strip()[:13]:
                        origin = line[line.find("{") + 1 : line.rfind("}")]
                if "Comment" == record_id:
                    continue
                if "NA" == record_id:
                    logging.error(f"Skipping record without ID: {record_string}")
                    continue

                status_data["IDs"].append(record_id)

                for org in origin.split(";"):
                    status_data["origin_list"].append([record_id, org])

                if (
                    str(status)
                    in colrev.record.RecordState.get_post_md_processed_states()
                ):
                    for origin_part in origin.split(";"):
                        status_data["persisted_IDs"].append([origin_part, record_id])

                if file_path != "NA":
                    if not all(Path(f).is_file() for f in file_path.split(";")):
                        status_data["pdf_not_exists"].append(record_id)

                if origin != "NA":
                    for org in origin.split(";"):
                        status_data["record_links_in_bib"].append(org)
                else:
                    status_data["entries_without_origin"].append(record_id)

                status_data["status_fields"].append(status)

                if "not_set" != excl_crit:
                    ec_case = [record_id, status, excl_crit]
                    status_data["screening_criteria_list"].append(ec_case)

                # TODO : the origins of a record could be in multiple states
                if "colrev_status" in prior:
                    prior_status = [
                        stat
                        for (org, stat) in prior["colrev_status"]
                        if org in origin.split(";")
                    ]
                else:
                    prior_status = []

                status_transition = {}
                if len(prior_status) == 0:
                    status_transition[record_id] = "load"
                else:
                    proc_transition_list: list = [
                        x["trigger"]
                        for x in colrev.process.ProcessModel.transitions
                        if str(x["source"]) == prior_status[0]
                        and str(x["dest"]) == status
                    ]
                    if len(proc_transition_list) == 0 and prior_status[0] != status:
                        status_data["start_states"].append(prior_status[0])
                        if prior_status[0] not in [
                            str(x) for x in colrev.record.RecordState
                        ]:
                            raise colrev_exceptions.StatusFieldValueError(
                                record_id, "colrev_status", prior_status[0]
                            )
                        if status not in [str(x) for x in colrev.record.RecordState]:
                            raise colrev_exceptions.StatusFieldValueError(
                                record_id, "colrev_status", status
                            )

                        status_data["invalid_state_transitions"].append(
                            f"{record_id}: {prior_status[0]} to {status}"
                        )
                    if 0 == len(proc_transition_list):
                        status_transition[record_id] = "load"
                    else:
                        proc_transition = proc_transition_list.pop()
                        status_transition[record_id] = proc_transition

                status_data["status_transitions"].append(status_transition)

        return status_data

    def retrieve_prior(self) -> dict:

        records_file_relative = self.review_manager.paths["RECORDS_FILE_RELATIVE"]
        revlist = (
            (
                commit.hexsha,
                (commit.tree / str(records_file_relative)).data_stream.read(),
            )
            for commit in self.__git_repo.iter_commits(paths=str(records_file_relative))
        )
        prior: dict = {"colrev_status": [], "persisted_IDs": []}
        filecontents = list(revlist)[0][1]
        prior_db_str = io.StringIO(filecontents.decode("utf-8"))
        for record_string in self.__read_next_record_str(file_object=prior_db_str):

            record_id, status, origin = "NA", "NA", "NA"
            for line in record_string.split("\n"):
                if "@" in line[:3]:
                    record_id = line[line.find("{") + 1 : line.rfind(",")]
                if "colrev_status" == line.lstrip()[:13]:
                    status = line[line.find("{") + 1 : line.rfind("}")]
                if "colrev_origin" == line.strip()[:13]:
                    origin = line[line.find("{") + 1 : line.rfind("}")]
            if "NA" != record_id:
                for orig in origin.split(";"):
                    prior["colrev_status"].append([orig, status])
                    if str(colrev.record.RecordState.md_processed) == status:
                        prior["persisted_IDs"].append([orig, record_id])

            else:
                logging.error(f"record without ID: {record_string}")

        return prior

    def retrieve_ids_from_bib(self, *, file_path: Path) -> list:
        assert file_path.suffix == ".bib"
        record_ids = []
        with open(file_path, encoding="utf8") as file:
            line = file.readline()
            while line:
                if "@" in line[:5]:
                    record_id = line[line.find("{") + 1 : line.rfind(",")]
                    record_ids.append(record_id.lstrip())
                line = file.readline()
        return record_ids

    def retrieve_by_colrev_id(
        self, *, indexed_record_dict: dict, records: list[dict]
    ) -> dict:

        indexed_record = colrev.record.Record(data=indexed_record_dict)

        if "colrev_id" in indexed_record.data:
            cid_to_retrieve = indexed_record.get_colrev_id()
        else:
            cid_to_retrieve = [indexed_record.create_colrev_id()]

        record_l = [
            x
            for x in records
            if any(
                cid in colrev.record.Record(data=x).get_colrev_id()
                for cid in cid_to_retrieve
            )
        ]
        if len(record_l) != 1:
            raise colrev_exceptions.RecordNotInRepoException
        return record_l[0]

    def update_colrev_ids(self) -> None:

        self.review_manager.logger.info("Create colrev_id list from origins")
        recs_dict = self.load_records_dict()
        if len(recs_dict) > 0:
            origin_records = self.load_origin_records()
            for rec in tqdm(recs_dict.values()):
                record = colrev.record.Record(data=rec)
                try:
                    colrev_id = record.create_colrev_id()
                    record.data["colrev_id"] = [colrev_id]
                except colrev_exceptions.NotEnoughDataToIdentifyException:
                    continue
                origins = record.get_origins()
                record.add_colrev_ids(
                    records=[
                        origin_records[origin]
                        for origin in set(origins)
                        if origin in origin_records
                    ]
                )

            # Note : we may create origins from history for curated repositories
            # for history_recs in self.load_from_git_history():
            #     for hist_rec in tqdm(history_recs.values()):
            #         for rec in recs_dict.values():
            #             record = Record(rec)
            #             HIST_RECORD = Record(hist_rec)
            #             # TODO : acces hist_rec based on an origin-key record-list?
            #             if record.shares_origins(HIST_RECORD):
            #                 record.add_colrev_ids([HIST_RECORD.get_data()])

            self.save_records_dict(records=recs_dict)
            self.add_record_changes()

    def get_next_id(self, *, bib_file: Path) -> int:
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

    def get_missing_files(self) -> list:

        # excluding pdf_not_available
        file_required_status = [
            str(colrev.record.RecordState.pdf_imported),
            str(colrev.record.RecordState.pdf_needs_manual_preparation),
            str(colrev.record.RecordState.pdf_prepared),
            str(colrev.record.RecordState.rev_excluded),
            str(colrev.record.RecordState.rev_included),
            str(colrev.record.RecordState.rev_synthesized),
        ]
        missing_files = []
        if self.review_manager.paths["RECORDS_FILE"].is_file():
            for record_header_item in self.__read_record_header_items():
                if (
                    record_header_item["colrev_status"] in file_required_status
                    and "NA" == record_header_item["file"]
                ):
                    missing_files.append(record_header_item["ID"])
        return missing_files

    def import_file(self, *, record: dict) -> dict:
        self.review_manager.paths["PDF_DIRECTORY_RELATIVE"].mkdir(exist_ok=True)
        new_fp = (
            self.review_manager.paths["PDF_DIRECTORY_RELATIVE"]
            / Path(record["ID"] + ".pdf").name
        )
        original_fp = Path(record["file"])

        if "symlink" == self.review_manager.settings.pdf_get.pdf_path_type:
            if not new_fp.is_file():
                new_fp.symlink_to(original_fp)
            record["file"] = str(new_fp)
        elif "copy" == self.review_manager.settings.pdf_get.pdf_path_type:
            if not new_fp.is_file():
                shutil.copyfile(original_fp, new_fp.resolve())
            record["file"] = str(new_fp)
        # Note : else: leave absolute paths

        return record

    @classmethod
    def inplace_change(
        cls, *, filename: Path, old_string: str, new_string: str
    ) -> None:
        with open(filename, encoding="utf8") as file:
            content = file.read()
            if old_string not in content:
                return
        with open(filename, "w", encoding="utf8") as file:
            content = content.replace(old_string, new_string)
            file.write(content)

    # CHECKS --------------------------------------------------------------

    def check_main_records_duplicates(self, *, status_data: dict) -> None:

        if not len(status_data["IDs"]) == len(set(status_data["IDs"])):
            duplicates = [
                ID for ID in status_data["IDs"] if status_data["IDs"].count(ID) > 1
            ]
            if len(duplicates) > 20:
                raise colrev_exceptions.DuplicateIDsError(
                    "Duplicates in RECORDS_FILE: "
                    f"({','.join(duplicates[0:20])}, ...)"
                )
            raise colrev_exceptions.DuplicateIDsError(
                f"Duplicates in RECORDS_FILE: {','.join(duplicates)}"
            )

    def check_main_records_origin(self, *, status_data: dict) -> None:

        # Check whether each record has an origin
        if not len(status_data["entries_without_origin"]) == 0:
            raise colrev_exceptions.OriginError(
                f"Entries without origin: {', '.join(status_data['entries_without_origin'])}"
            )

        # Check for broken origins
        search_dir = self.review_manager.paths["SEARCHDIR"]
        all_record_links = []
        for bib_file in search_dir.glob("*.bib"):
            search_ids = self.retrieve_ids_from_bib(file_path=bib_file)
            for search_id in search_ids:
                all_record_links.append(bib_file.name + "/" + search_id)
        delta = set(status_data["record_links_in_bib"]) - set(all_record_links)
        if len(delta) > 0:
            raise colrev_exceptions.OriginError(f"broken origins: {delta}")

        # Check for non-unique origins
        origins = list(itertools.chain(*status_data["origin_list"]))
        non_unique_origins = []
        for org in origins:
            if origins.count(org) > 1:
                non_unique_origins.append(org)
        if non_unique_origins:
            for _, org in status_data["origin_list"]:
                if org in non_unique_origins:
                    raise colrev_exceptions.OriginError(
                        f'Non-unique origin: origin="{org}"'
                    )

        # TODO : Check for removed origins
        # add to method signature: (..., prior: dict, ...)
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
        #                     "ID of processed record changed from"
        #                     f" {prior_id} to {new_id}"
        #                 )
        #                 check_propagated_ids(prior_id, new_id)
        #                 STATUS = FAIL

    def check_fields(self, *, status_data: dict) -> None:
        # Check status fields
        status_schema = [str(x) for x in colrev.record.RecordState]
        stat_diff = set(status_data["status_fields"]).difference(status_schema)
        if stat_diff:
            raise colrev_exceptions.FieldValueError(
                f"status field(s) {stat_diff} not in {status_schema}"
            )

    def check_status_transitions(self, *, status_data: dict) -> None:
        if len(set(status_data["start_states"])) > 1:
            raise colrev_exceptions.StatusTransitionError(
                "multiple transitions from different "
                f'start states ({set(status_data["start_states"])})'
            )
        if len(set(status_data["invalid_state_transitions"])) > 0:
            raise colrev_exceptions.StatusTransitionError(
                "invalid state transitions: \n    "
                + "\n    ".join(status_data["invalid_state_transitions"])
            )

    def __get_screening_criteria(self, *, ec_string: str) -> list:
        excl_criteria = [ec.split("=")[0] for ec in ec_string.split(";") if ec != "NA"]
        if [""] == excl_criteria:
            excl_criteria = []
        return excl_criteria

    def check_corrections_of_curated_records(self) -> None:
        # pylint: disable=redefined-outer-name

        if not self.records_file.is_file():
            return

        self.review_manager.logger.debug("Start corrections")

        local_index = self.review_manager.get_local_index()

        # TODO : remove the following:
        # from colrev.prep import Preparation
        # self.PREPARATION = Preparation(
        #     review_manager=self.review_manager, notify_state_transition_operation=False
        # )

        # pylint: disable=duplicate-code
        essential_md_keys = [
            "title",
            "author",
            "journal",
            "year",
            "booktitle",
            "number",
            "volume",
            "issue",
            "author",
            "doi",
            "colrev_origin",  # Note : for merges
        ]

        self.review_manager.logger.debug("Retrieve prior bib")
        records_file_relative = self.review_manager.paths["RECORDS_FILE_RELATIVE"]
        revlist = (
            (
                commit.hexsha,
                (commit.tree / str(records_file_relative)).data_stream.read(),
            )
            for commit in self.__git_repo.iter_commits(paths=str(records_file_relative))
        )
        prior: dict = {"curated_records": []}

        try:
            filecontents = list(revlist)[0][1]
        except IndexError:
            return

        self.review_manager.logger.debug("Load prior bib")
        prior_db_str = io.StringIO(filecontents.decode("utf-8"))
        for record_string in self.__read_next_record_str(file_object=prior_db_str):

            # TBD: whether/how to detect dblp. Previously:
            # if any(x in record_string for x in ["{CURATED:", "{DBLP}"]):
            if "{CURATED:" in record_string:
                records_dict = self.load_records_dict(load_str=record_string)
                record_dict = list(records_dict.values())[0]
                prior["curated_records"].append(record_dict)

        self.review_manager.logger.debug("Load current bib")
        curated_records = []
        with open(self.records_file, encoding="utf8") as file:
            for record_string in self.__read_next_record_str(file_object=file):

                # TBD: whether/how to detect dblp. Previously:
                # if any(x in record_string for x in ["{CURATED:", "{DBLP}"]):
                if "{CURATED:" in record_string:
                    records_dict = self.load_records_dict(load_str=record_string)
                    record_dict = list(records_dict.values())[0]
                    curated_records.append(record_dict)

        resources = self.review_manager.get_resources()
        for curated_record in curated_records:

            # TODO : use origin-indexed dict (discarding changes during merges)

            # identify curated records for which essential metadata is changed
            prior_crl = [
                x
                for x in prior["curated_records"]
                if any(
                    y in curated_record["colrev_origin"].split(";")
                    for y in x["colrev_origin"].split(";")
                )
            ]

            if len(prior_crl) == 0:
                self.review_manager.logger.debug("No prior records found")
                continue

            for prior_cr in prior_crl:

                if not all(
                    prior_cr.get(k, "NA") == curated_record.get(k, "NA")
                    for k in essential_md_keys
                ):
                    # after the previous condition, we know that the curated record
                    # has been corrected
                    corrected_curated_record = curated_record.copy()
                    if colrev.record.Record(
                        data=corrected_curated_record
                    ).masterdata_is_curated():
                        # retrieve record from index to identify origin repositories
                        try:
                            original_curated_record = local_index.retrieve(
                                record_dict=prior_cr
                            )

                            # Note : this is a simple heuristic:
                            curation_path = resources.curations_path / Path(
                                original_curated_record["colrev_masterdata_provenance"][
                                    "source"
                                ].split("/")[-1]
                            )
                            if not curation_path.is_dir():
                                prov_inf = original_curated_record[
                                    "colrev_masterdata_provenance"
                                ]["source"]
                                print(
                                    "Source path of indexed record not available "
                                    f'({original_curated_record["ID"]} - '
                                    f"{prov_inf})"
                                )
                                continue
                        except (colrev_exceptions.RecordNotInIndexException, KeyError):
                            original_curated_record = prior_cr.copy()

                        original_curated_record["colrev_id"] = colrev.record.Record(
                            data=original_curated_record
                        ).create_colrev_id()

                    else:
                        continue  # probably?

                    # Cast to string for persistence
                    original_curated_record = {
                        k: str(v) for k, v in original_curated_record.items()
                    }
                    corrected_curated_record = {
                        k: str(v) for k, v in corrected_curated_record.items()
                    }

                    # Note : removing the fields is a temporary fix
                    # because the subsetting of change_items does not seem to
                    # work properly
                    if "pages" in original_curated_record:
                        del original_curated_record["pages"]
                    if "pages" in corrected_curated_record:
                        del corrected_curated_record["pages"]
                    # if "dblp_key" in corrected_curated_record:
                    #     del corrected_curated_record["dblp_key"]
                    if "colrev_status" in corrected_curated_record:
                        del corrected_curated_record["colrev_status"]

                    if "colrev_status" in original_curated_record:
                        del original_curated_record["colrev_status"]

                    # TODO : export only essential changes?
                    changes = diff(original_curated_record, corrected_curated_record)
                    change_items = list(changes)

                    keys_to_ignore = [
                        "screening_criteria",
                        "colrev_status",
                        "source_url",
                        "metadata_source_repository_paths",
                        "ID",
                        "grobid-version",
                        "colrev_pdf_id",
                        "file",
                        "colrev_origin",
                        "colrev_data_provenance",
                        "sem_scholar_id",
                    ]

                    selected_change_items = []
                    for change_item in change_items:
                        change_type, key, val = change_item
                        if "add" == change_type:
                            for add_item in val:
                                add_item_key, add_item_val = add_item
                                if add_item_key not in keys_to_ignore:
                                    selected_change_items.append(
                                        ("add", "", [(add_item_key, add_item_val)])
                                    )
                        elif "change" == change_type:
                            if key not in keys_to_ignore:
                                selected_change_items.append(change_item)

                    change_items = selected_change_items

                    if len(change_items) == 0:
                        continue

                    if len(
                        corrected_curated_record.get("colrev_origin", "").split(";")
                    ) > len(
                        original_curated_record.get("colrev_origin", "").split(";")
                    ):
                        if (
                            "dblp_key" in corrected_curated_record
                            and "dblp_key" in original_curated_record
                        ):
                            if (
                                corrected_curated_record["dblp_key"]
                                != original_curated_record["dblp_key"]
                            ):
                                change_items = {  # type: ignore
                                    "merge": [
                                        corrected_curated_record["dblp_key"],
                                        original_curated_record["dblp_key"],
                                    ]
                                }
                        # else:
                        #     change_items = {
                        #         "merge": [
                        #             corrected_curated_record["ID"],
                        #             original_curated_record["ID"],
                        #         ]
                        #     }

                    # TODO : cover non-masterdata corrections
                    if "colrev_masterdata_provenance" not in original_curated_record:
                        continue

                    dict_to_save = {
                        "source_url": original_curated_record[
                            "colrev_masterdata_provenance"
                        ],
                        "original_curated_record": original_curated_record,
                        "changes": change_items,
                    }
                    filepath = self.review_manager.paths["CORRECTIONS_PATH"] / Path(
                        f"{curated_record['ID']}.json"
                    )
                    filepath.parent.mkdir(exist_ok=True)

                    with open(filepath, "w", encoding="utf8") as corrections_file:
                        json.dump(dict_to_save, corrections_file, indent=4)

                    # TODO : combine merge-record corrections

        # for testing:
        # raise KeyError

    def check_main_records_screen(self, *, status_data: dict) -> None:

        # Check screen
        # Note: consistency of inclusion_2=yes -> inclusion_1=yes
        # is implicitly ensured through status
        # (screen2-included/excluded implies prescreen included!)

        field_errors = []

        if status_data["screening_criteria_list"]:
            screening_criteria = status_data["screening_criteria_list"][0][2]
            if screening_criteria != "NA":
                criteria = self.__get_screening_criteria(ec_string=screening_criteria)
                settings_criteria = list(
                    self.review_manager.settings.screen.criteria.keys()
                )
                if not set(criteria) == set(settings_criteria):
                    field_errors.append(
                        "Mismatch in screening criteria: records:"
                        f" {criteria} vs. settings: {settings_criteria}"
                    )
                pattern = "=(in|out);".join(criteria) + "=(in|out)"
                pattern_inclusion = "=in;".join(criteria) + "=in"
            else:
                criteria = ["NA"]
                pattern = "^NA$"
                pattern_inclusion = "^NA$"
            for [record_id, status, excl_crit] in status_data[
                "screening_criteria_list"
            ]:
                # print([record_id, status, excl_crit])
                if not re.match(pattern, excl_crit):
                    # Note: this should also catch cases of missing
                    # screening criteria
                    field_errors.append(
                        "Screening criteria field not matching "
                        f"pattern: {excl_crit} ({record_id}; criteria: {criteria})"
                    )

                elif str(colrev.record.RecordState.rev_excluded) == status:
                    if ["NA"] == criteria:
                        if "NA" == excl_crit:
                            continue
                        field_errors.append(f"excl_crit field not NA: {excl_crit}")

                    if "=out" not in excl_crit:
                        logging.error(f"criteria: {criteria}")
                        field_errors.append(
                            "Excluded record with no screening_criterion violated: "
                            f"{record_id}, {status}, {excl_crit}"
                        )

                # Note: we don't have to consider the cases of
                # status=retrieved/prescreen_included/prescreen_excluded
                # because they would not have screening_criteria.
                elif status in [
                    str(colrev.record.RecordState.rev_included),
                    str(colrev.record.RecordState.rev_synthesized),
                ]:
                    if not re.match(pattern_inclusion, excl_crit):
                        field_errors.append(
                            "Included record with screening_criterion satisfied: "
                            f"{record_id}, {status}, {excl_crit}"
                        )
                else:
                    if not re.match(pattern_inclusion, excl_crit):
                        field_errors.append(
                            "Record with screening_criterion but before "
                            f"screen: {record_id}, {status}"
                        )
        if len(field_errors) > 0:
            raise colrev_exceptions.FieldValueError(
                "\n    " + "\n    ".join(field_errors)
            )

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
    #     # Check consistency: all IDs in data.csv in records.bib
    #     missing_IDs = [ID for
    #                    ID in data['ID'].tolist()
    #                    if ID not in IDs]
    #     if not len(missing_IDs) == 0:
    #         raise some error ('IDs in data.csv not in RECORDS_FILE: ' +
    #               str(set(missing_IDs)))
    #     return

    def check_propagated_ids(self, *, prior_id: str, new_id: str) -> list:

        ignore_patterns = [
            ".git",
            "report.log",
            ".pre-commit-config.yaml",
        ]

        text_formats = [".txt", ".csv", ".md", ".bib", ".yaml"]
        notifications = []
        for root, dirs, files in os.walk(self.review_manager.path, topdown=False):
            for name in files:
                if any((x in name) or (x in root) for x in ignore_patterns):
                    continue
                if prior_id in name:
                    msg = (
                        f"Old ID ({prior_id}, changed to {new_id} in the "
                        + f"RECORDS_FILE) found in filepath: {name}"
                    )
                    if msg not in notifications:
                        notifications.append(msg)

                if not any(name.endswith(x) for x in text_formats):
                    logging.debug(f"Skipping {name}")
                    continue
                logging.debug(f"Checking {name}")
                if name.endswith(".bib"):
                    retrieved_ids = self.retrieve_ids_from_bib(
                        file_path=Path(os.path.join(root, name))
                    )
                    if prior_id in retrieved_ids:
                        msg = (
                            f"Old ID ({prior_id}, changed to {new_id} in "
                            + f"the RECORDS_FILE) found in file: {name}"
                        )
                        if msg not in notifications:
                            notifications.append(msg)
                else:
                    with open(os.path.join(root, name), encoding="utf8") as file:
                        line = file.readline()
                        while line:
                            if name.endswith(".bib") and "@" in line[:5]:
                                line = file.readline()
                            if prior_id in line:
                                msg = (
                                    f"Old ID ({prior_id}, to {new_id} in "
                                    + f"the RECORDS_FILE) found in file: {name}"
                                )
                                if msg not in notifications:
                                    notifications.append(msg)
                            line = file.readline()
            for name in dirs:
                if any((x in name) or (x in root) for x in ignore_patterns):
                    continue
                if prior_id in name:
                    notifications.append(
                        f"Old ID ({prior_id}, changed to {new_id} in the "
                        f"RECORDS_FILE) found in filepath: {name}"
                    )
        return notifications

    def check_persisted_id_changes(self, *, prior: dict, status_data: dict) -> None:
        if "persisted_IDs" not in prior:
            return
        for prior_origin, prior_id in prior["persisted_IDs"]:
            if prior_origin not in [x[0] for x in status_data["persisted_IDs"]]:
                # Note: this does not catch origins removed before md_processed
                raise colrev_exceptions.OriginError(f"origin removed: {prior_origin}")
            for new_origin, new_id in status_data["persisted_IDs"]:
                if new_origin == prior_origin:
                    if new_id != prior_id:
                        notifications = self.check_propagated_ids(
                            prior_id=prior_id, new_id=new_id
                        )
                        notifications.append(
                            "ID of processed record changed from "
                            f"{prior_id} to {new_id}"
                        )
                        raise colrev_exceptions.PropagatedIDChange(notifications)

    def check_sources(self) -> None:

        for source in self.review_manager.settings.sources:

            if not source.filename.is_file():
                self.review_manager.logger.debug(
                    f"Search details without file: {source.filename}"
                )

            # date_regex = r"^\d{4}-\d{2}-\d{2}$"
            # if "completion_date" in source:
            #     if not re.search(date_regex, source["completion_date"]):
            #         raise SearchSettingsError(
            #             "completion date not matching YYYY-MM-DD format: "
            #             f'{source["completion_date"]}'
            #         )
            # if "start_date" in source:
            #     if not re.search(date_regex, source["start_date"]):
            #         raise SearchSettingsError(
            #             "start_date date not matchin YYYY-MM-DD format: "
            #             f'{source["start_date"]}'
            #         )

    # GIT operations -----------------------------------------------

    def get_repo(self) -> git.Repo:
        """Get the git repository object (requires review_manager.notify(...))"""

        if self.review_manager.notified_next_process is None:
            raise colrev_exceptions.ReviewManagerNotNofiedError()
        return self.__git_repo

    def has_changes(self) -> bool:
        # Extension : allow for optional path (check changes for that file)
        return self.__git_repo.is_dirty()

    def add_changes(self, *, path: Path) -> None:

        while (self.review_manager.path / Path(".git/index.lock")).is_file():
            time.sleep(0.5)
            print("Waiting for previous git operation to complete")

        self.__git_repo.index.add([str(path)])

    def get_untracked_files(self) -> list:
        return self.__git_repo.untracked_files

    def remove_file_from_git(self, *, path: str) -> None:

        self.__git_repo.index.remove(
            [path],
            working_tree=True,
        )

    def create_commit(
        self, *, msg: str, author: git.Actor, committer: git.Actor, hook_skipping: bool
    ) -> None:
        self.__git_repo.index.commit(
            msg,
            author=author,
            committer=committer,
            skip_hooks=hook_skipping,
        )

    def file_in_history(self, *, filepath: Path) -> bool:
        return str(filepath) in [x.path for x in self.__git_repo.head.commit.tree]

    def get_commit_message(self, *, commit_nr: int) -> str:
        master = self.__git_repo.head.reference
        assert commit_nr == 0  # extension : implement other cases
        if commit_nr == 0:
            cmsg = master.commit.message
        return cmsg

    def add_record_changes(self) -> None:

        while (self.review_manager.path / Path(".git/index.lock")).is_file():
            time.sleep(0.5)
            print("Waiting for previous git operation to complete")
        self.__git_repo.index.add(
            [str(self.review_manager.paths["RECORDS_FILE_RELATIVE"])]
        )

    def add_setting_changes(self) -> None:

        while (self.review_manager.path / Path(".git/index.lock")).is_file():
            time.sleep(0.5)
            print("Waiting for previous git operation to complete")

        self.__git_repo.index.add([str(self.review_manager.paths["SETTINGS_RELATIVE"])])

    def reset_log_if_no_changes(self) -> None:
        if not self.__git_repo.is_dirty():
            self.review_manager.reset_log()

    def get_last_commit_sha(self) -> str:
        return str(self.__git_repo.head.commit.hexsha)

    def get_tree_hash(self) -> str:
        tree_hash = self.__git_repo.git.execute(["git", "write-tree"])
        return str(tree_hash)

    def get_remote_commit_differences(self) -> list:

        nr_commits_behind, nr_commits_ahead = -1, -1

        origin = self.__git_repo.remotes.origin
        if origin.exists():
            try:
                origin.fetch()
            except GitCommandError:
                return [-1, -1]

        if self.__git_repo.active_branch.tracking_branch() is not None:

            branch_name = str(self.__git_repo.active_branch)
            tracking_branch_name = str(self.__git_repo.active_branch.tracking_branch())
            self.review_manager.logger.debug(f"{branch_name} - {tracking_branch_name}")

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = self.__git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = self.__git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

        return [nr_commits_behind, nr_commits_ahead]

    def behind_remote(self) -> bool:
        nr_commits_behind = 0
        connected_remote = 0 != len(self.__git_repo.remotes)
        if connected_remote:
            origin = self.__git_repo.remotes.origin
            if origin.exists():
                (
                    nr_commits_behind,
                    _,
                ) = self.get_remote_commit_differences()
        if nr_commits_behind > 0:
            return True
        return False

    def remote_ahead(self) -> bool:
        connected_remote = 0 != len(self.__git_repo.remotes)
        if connected_remote:
            origin = self.__git_repo.remotes.origin
            if origin.exists():
                (
                    _,
                    nr_commits_ahead,
                ) = self.get_remote_commit_differences()
        if nr_commits_ahead > 0:
            return True
        return False

    def pull_if_repo_clean(self) -> None:
        if not self.__git_repo.is_dirty():
            origin = self.__git_repo.remotes.origin
            origin.pull()


if __name__ == "__main__":
    pass
