#!/usr/bin/env python3
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
import unicodedata
from copy import deepcopy
from pathlib import Path

import git
import pandas as pd
from dictdiffer import diff
from git.exc import GitCommandError
from tqdm import tqdm

import colrev_core.exceptions as colrev_exceptions
from colrev_core.process import FormatProcess
from colrev_core.process import ProcessModel
from colrev_core.record import PrepRecord
from colrev_core.record import Record
from colrev_core.record import RecordState
from colrev_core.settings import IDPpattern
from colrev_core.settings import SearchType


class ReviewDataset:
    def __init__(self, *, REVIEW_MANAGER) -> None:

        self.REVIEW_MANAGER = REVIEW_MANAGER
        self.RECORDS_FILE = REVIEW_MANAGER.paths["RECORDS_FILE"]
        self.__git_repo = git.Repo(self.REVIEW_MANAGER.path)

    def get_record_state_list(self) -> list:
        """Get the record_state_list"""

        if not self.RECORDS_FILE.is_file():
            record_state_list = []
        else:
            record_state_list = self.__read_record_header_items()
        return record_state_list

    def get_origin_state_dict(self, *, file_object=None) -> dict:
        ret_dict = {}
        if self.RECORDS_FILE.is_file():
            for record_header_item in self.__read_record_header_items(
                file_object=file_object
            ):
                for origin in record_header_item["colrev_origin"].split(";"):
                    ret_dict[origin] = record_header_item["colrev_status"]

        return ret_dict

    def get_record_header_list(self) -> list:
        """Get the record_header_list"""

        if not self.RECORDS_FILE.is_file():
            return []
        return self.__read_record_header_items()

    def get_currently_imported_origin_list(self) -> list:
        record_header_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_header_list()
        imported_origins = [x["colrev_origin"].split(";") for x in record_header_list]
        imported_origins = list(itertools.chain(*imported_origins))
        return imported_origins

    def get_states_set(self, *, record_state_list: list = None) -> set:
        """Get the record_states_set"""

        if not self.RECORDS_FILE.is_file():
            return set()
        if record_state_list is None:
            record_state_list = self.get_record_state_list()
        return {el["colrev_status"] for el in record_state_list}

    def retrieve_records_from_history(
        self,
        *,
        original_records: typing.List[typing.Dict],
        condition_state: RecordState,
    ) -> typing.List:

        prior_records = []
        RECORDS_FILE_RELATIVE = self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]
        git_repo = self.__git_repo
        revlist = (
            (
                commit.hexsha,
                commit.message,
                (commit.tree / str(RECORDS_FILE_RELATIVE)).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(RECORDS_FILE_RELATIVE))
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
            s = ""
            if last:
                s += join([prelast, last])
            if lineage:
                s += f", {lineage}"
            if first or middle:
                s += ", "
                s += join([first, middle])
            return s

        # Need to concatenate fields and persons dicts
        # but pybtex is still the most efficient solution.
        records_dict = {
            k: {
                **{"ID": k},
                **{"ENTRYTYPE": v.type},
                **dict(
                    {
                        # Cast status to Enum
                        k: RecordState[v] if ("colrev_status" == k)
                        # DOIs are case sensitive -> use upper case.
                        else v.upper()
                        if ("doi" == k)
                        else [el.rstrip() for el in (v + " ").split("; ") if "" != el]
                        if k in Record.list_fields_keys
                        else ReviewDataset.load_field_dict(value=v, field=k)
                        if k in Record.dict_fields_keys
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
        """Get the records (requires REVIEW_MANAGER.notify(...))"""
        from pybtex.database.input import bibtex

        # TODO : optional dict-key as a parameter

        import pybtex.errors

        pybtex.errors.set_strict_mode(False)

        if self.REVIEW_MANAGER.notified_next_process is None:
            raise colrev_exceptions.ReviewManagerNotNofiedError()

        RECORDS_FILE = self.REVIEW_MANAGER.paths["RECORDS_FILE"]
        parser = bibtex.Parser()

        if load_str:
            bib_data = parser.parse_string(load_str)
            records_dict = self.parse_records_dict(records_dict=bib_data.entries)

        elif RECORDS_FILE.is_file():
            bib_data = parser.parse_file(RECORDS_FILE)
            records_dict = self.parse_records_dict(records_dict=bib_data.entries)
        else:
            records_dict = {}

        return records_dict

    def load_origin_records(self) -> dict:

        origin_records: typing.Dict[str, typing.Any] = {}
        sources = [x.filename for x in self.REVIEW_MANAGER.sources]
        for source in sources:
            source_file = self.REVIEW_MANAGER.paths["SEARCHDIR_RELATIVE"] / Path(source)
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
        RECORDS_FILE_RELATIVE = self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]
        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        revlist = (
            (
                commit.hexsha,
                commit.message,
                (commit.tree / str(RECORDS_FILE_RELATIVE)).data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths=str(RECORDS_FILE_RELATIVE))
        )

        for _, _, filecontents in list(revlist):
            prior_records_dict = self.load_records_dict(load_str=filecontents)

            records_dict = {
                r["ID"]: {
                    k: RecordState[v]
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
    def parse_bibtex_str(cls, *, recs_dict_in) -> str:

        # Note: we need a deepcopy because the parsing modifies dicts
        recs_dict = deepcopy(recs_dict_in)

        def format_field(field, value) -> str:
            padd = " " * max(0, 28 - len(field))
            return f",\n   {field} {padd} = {{{value}}}"

        bibtex_str = ""

        first = True
        for ID, record in recs_dict.items():
            if not first:
                bibtex_str += "\n"
            first = False

            bibtex_str += f"@{record['ENTRYTYPE']}"
            bibtex_str += "{%s" % ID

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

            RECORD = Record(data=record)
            record = RECORD.get_data(stringify=True)

            for ordered_field in field_order:
                if ordered_field in record:
                    if "" == record[ordered_field]:
                        continue
                    bibtex_str += format_field(ordered_field, record[ordered_field])

            for key, value in record.items():
                if key in field_order + ["ID", "ENTRYTYPE"]:
                    continue

                bibtex_str += format_field(key, value)

            bibtex_str += ",\n}\n"

        return bibtex_str

    @classmethod
    def save_records_dict_to_file(cls, *, records, save_path: Path):
        """Save the records dict to specifified file"""
        # Note : this classmethod function can be called by CoLRev scripts
        # operating outside a CoLRev repo (e.g., sync)

        bibtex_str = ReviewDataset.parse_bibtex_str(recs_dict_in=records)

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

    def save_records_dict(self, *, records) -> None:
        """Save the records dict in RECORDS_FILE"""

        RECORDS_FILE = self.REVIEW_MANAGER.paths["RECORDS_FILE"]
        self.save_records_dict_to_file(records=records, save_path=RECORDS_FILE)

    def reprocess_id(self, *, paper_ids: str) -> None:
        """Remove an ID (set of IDs) from the bib_db (for reprocessing)"""

        saved_args = locals()

        if "all" == paper_ids:
            # logging.info("Removing/reprocessing all records")
            os.remove(self.RECORDS_FILE)
            self.__git_repo.index.remove(
                [str(self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"])],
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

        self.REVIEW_MANAGER.create_commit(msg="Reprocess", saved_args=saved_args)

    def set_IDs(
        self, *, records: typing.Dict = None, selected_IDs: list = None
    ) -> typing.Dict:
        """Set the IDs of records according to predefined formats or
        according to the LocalIndex"""
        from colrev_core.environment import LocalIndex

        if records is None:
            records = {}

        self.LOCAL_INDEX = LocalIndex()

        if len(records) == 0:
            records = self.load_records_dict()

        ID_list = list(records.keys())

        for record_ID in list(records.keys()):
            record = records[record_ID]
            RECORD = Record(data=record)
            if RECORD.masterdata_is_curated():
                continue
            self.REVIEW_MANAGER.logger.debug(f"Set ID for {record_ID}")
            if selected_IDs is not None:
                if record_ID not in selected_IDs:
                    continue
            elif str(record["colrev_status"]) not in [
                str(RecordState.md_imported),
                str(RecordState.md_prepared),
            ]:
                continue

            old_id = record_ID
            new_id = self.__generate_ID_blacklist(
                record=record,
                ID_blacklist=ID_list,
                record_in_bib_db=True,
                raise_error=False,
            )

            ID_list.append(new_id)
            if old_id != new_id:
                # We need to insert the a new element into records
                # to make sure that the IDs are actually saved
                record.update(ID=new_id)
                records[new_id] = record
                del records[old_id]
                self.REVIEW_MANAGER.report_logger.info(f"set_ID({old_id}) to {new_id}")
                if old_id in ID_list:
                    ID_list.remove(old_id)

        self.save_records_dict(records=records)
        # Note : temporary fix
        # (to prevent failing format checks caused by special characters)

        # records = self.load_records_dict()
        # self.save_records_dict(records=records)
        self.add_record_changes()

        return records

    def propagated_ID(self, *, ID: str) -> bool:
        """Check whether an ID has been propagated"""

        propagated = False

        if self.REVIEW_MANAGER.paths["DATA"].is_file():
            # Note: this may be redundant, but just to be sure:
            data = pd.read_csv(self.REVIEW_MANAGER.paths["DATA"], dtype=str)
            if ID in data["ID"].tolist():
                propagated = True

        # TODO : also check data_pages?

        return propagated

    def __generate_ID_blacklist(
        self,
        *,
        record: dict,
        ID_blacklist: list = None,
        record_in_bib_db: bool = False,
        raise_error: bool = True,
    ) -> str:
        """Generate a blacklist to avoid setting duplicate IDs"""

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
            return wo_ac

        # Make sure that IDs that have been propagated to the
        # screen or data will not be replaced
        # (this would break the chain of evidence)
        if raise_error:
            if self.propagated_ID(ID=record["ID"]):
                raise colrev_exceptions.PropagatedIDChange([record["ID"]])
        try:
            retrieved_record = self.LOCAL_INDEX.retrieve(record=record)
            temp_ID = retrieved_record["ID"]
        except colrev_exceptions.RecordNotInIndexException:

            if "" != record.get("author", record.get("editor", "")):
                authors_string = record.get("author", record.get("editor", "Anonymous"))
                authors = PrepRecord.format_author_field(
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

            ID_PATTERN = self.REVIEW_MANAGER.settings.project.id_pattern

            if IDPpattern.first_author_year == ID_PATTERN:
                temp_ID = (
                    f'{author.replace(" ", "")}{str(record.get("year", "NoYear"))}'
                )

            if IDPpattern.three_authors_year == ID_PATTERN:
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
            while next_unique_ID.lower() in [i.lower() for i in other_ids]:
                if len(appends) == 0:
                    order += 1
                    appends = list(itertools.product(letters, repeat=order))
                next_unique_ID = temp_ID + "".join(list(appends.pop(0)))
            temp_ID = next_unique_ID

        return temp_ID

    def __read_record_header_items(self, *, file_object=None) -> list:

        # Note : more than 10x faster than load_records_dict()

        def parse_k_v(current_key_value_pair_str):
            if " = " in current_key_value_pair_str:
                k, v = current_key_value_pair_str.split(" = ", 1)
            else:
                k = "ID"
                v = current_key_value_pair_str.split("{")[1]

            k = k.lstrip().rstrip()
            v = v.lstrip().rstrip().lstrip("{").rstrip("},")
            return k, v

        record_header_items = []
        if file_object is None:
            with open(self.RECORDS_FILE, encoding="utf-8") as file_object:

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

                    if (
                        current_header_item_count > number_required_header_items
                        or "}" == line
                    ):
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
                        k, v = parse_k_v(current_key_value_pair_str)
                        current_key_value_pair_str = ""
                        if k in record_header_item:
                            current_header_item_count += 1
                            record_header_item[k] = v

                record_header_items.append(record_header_item)
        return record_header_items

    def __read_next_record_str(self, *, file_object=None) -> typing.Iterator[str]:
        def yield_from_file(f):
            data = ""
            first_entry_processed = False
            while True:
                line = f.readline()
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
            with open(self.RECORDS_FILE, encoding="utf8") as records_file_object:
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

    def replace_field(self, *, IDs: list, key: str, val_str: str) -> None:

        val = val_str.encode("utf-8")
        current_ID_str = "NA"
        with open(self.RECORDS_FILE, "r+b") as fd:
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

    def update_record_by_ID(self, *, new_record: dict, delete: bool = False) -> None:

        new_record_dict = {new_record["ID"]: new_record}
        replacement = ReviewDataset.parse_bibtex_str(recs_dict_in=new_record_dict)

        current_ID_str = "NA"
        with open(self.RECORDS_FILE, "r+b") as fd:
            seekpos = fd.tell()
            line = fd.readline()
            while line:
                if b"@" in line[:3]:
                    current_ID = line[line.find(b"{") + 1 : line.rfind(b",")]
                    current_ID_str = current_ID.decode("utf-8")

                if current_ID_str == new_record["ID"]:
                    line = fd.readline()
                    while (
                        b"@" not in line[:3] and line
                    ):  # replace: drop the current record
                        line = fd.readline()
                    remaining = line + fd.read()
                    fd.seek(seekpos)
                    if not delete:
                        fd.write(replacement.encode("utf-8"))
                        fd.write(b"\n")
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

    def save_record_list_by_ID(
        self, *, record_list: list, append_new: bool = False
    ) -> None:

        if record_list == []:
            return

        record_dict = {r["ID"]: r for r in record_list}
        parsed = ReviewDataset.parse_bibtex_str(recs_dict_in=record_dict)

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
        if self.RECORDS_FILE.is_file():
            with open(self.RECORDS_FILE, "r+b") as fd:
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
                with open(self.RECORDS_FILE, "a", encoding="utf8") as m_refs:
                    for replacement in record_list:
                        m_refs.write(replacement["record"])

            else:
                self.REVIEW_MANAGER.report_logger.error(
                    "records not written to file: " f'{[x["ID"] for x in record_list]}'
                )

        self.add_record_changes()

    def format_records_file(self) -> bool:

        FormatProcess(REVIEW_MANAGER=self.REVIEW_MANAGER)  # to notify

        records = self.load_records_dict()
        for record in records.values():
            if "colrev_status" not in record:
                print(f'Error: no status field in record ({record["ID"]})')
                continue

            RECORD = PrepRecord(data=record)

            if record["colrev_status"] in [
                RecordState.md_needs_manual_preparation,
            ]:
                RECORD.update_masterdata_provenance(
                    UNPREPARED_RECORD=RECORD, REVIEW_MANAGER=self.REVIEW_MANAGER
                )
                RECORD.update_metadata_status(REVIEW_MANAGER=self.REVIEW_MANAGER)

            if record["colrev_status"] == RecordState.pdf_prepared:
                RECORD.reset_pdf_provenance_notes()

            record = RECORD.get_data()

        self.save_records_dict(records=records)
        CHANGED = self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"] in [
            r.a_path for r in self.__git_repo.index.diff(None)
        ]
        return CHANGED

    def retrieve_data(self, *, prior: dict) -> dict:

        data: dict = {
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

        with open(self.RECORDS_FILE, encoding="utf8") as f:
            for record_string in self.__read_next_record_str(file_object=f):
                ID, file, status, excl_crit, origin = (
                    "NA",
                    "NA",
                    "NA",
                    "not_set",
                    "NA",
                )

                for line in record_string.split("\n"):
                    if "@Comment" in line:
                        ID = "Comment"
                        break
                    if "@" in line[:3]:
                        ID = line[line.find("{") + 1 : line.rfind(",")]
                    if "file" == line.lstrip()[:4]:
                        file = line[line.find("{") + 1 : line.rfind("}")]
                    if "colrev_status" == line.lstrip()[:13]:
                        status = line[line.find("{") + 1 : line.rfind("}")]
                    if "screening_criteria" == line.lstrip()[:18]:
                        excl_crit = line[line.find("{") + 1 : line.rfind("}")]
                    if "colrev_origin" == line.strip()[:13]:
                        origin = line[line.find("{") + 1 : line.rfind("}")]
                if "Comment" == ID:
                    continue
                if "NA" == ID:
                    logging.error(f"Skipping record without ID: {record_string}")
                    continue

                data["IDs"].append(ID)

                for org in origin.split(";"):
                    data["origin_list"].append([ID, org])

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

                if "not_set" != excl_crit:
                    ec_case = [ID, status, excl_crit]
                    data["screening_criteria_list"].append(ec_case)

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
                    status_transition[ID] = "load"
                else:
                    proc_transition_list: list = [
                        x["trigger"]
                        for x in ProcessModel.transitions
                        if str(x["source"]) == prior_status[0]
                        and str(x["dest"]) == status
                    ]
                    if len(proc_transition_list) == 0 and prior_status[0] != status:
                        data["start_states"].append(prior_status[0])
                        if prior_status[0] not in [str(x) for x in RecordState]:
                            raise colrev_exceptions.StatusFieldValueError(
                                ID, "colrev_status", prior_status[0]
                            )
                        if status not in [str(x) for x in RecordState]:
                            raise colrev_exceptions.StatusFieldValueError(
                                ID, "colrev_status", status
                            )

                        data["invalid_state_transitions"].append(
                            f"{ID}: {prior_status[0]} to {status}"
                        )
                    if 0 == len(proc_transition_list):
                        status_transition[ID] = "load"
                    else:
                        proc_transition = proc_transition_list.pop()
                        status_transition[ID] = proc_transition

                data["status_transitions"].append(status_transition)

        return data

    def retrieve_prior(self) -> dict:

        RECORDS_FILE_RELATIVE = self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]
        revlist = (
            (
                commit.hexsha,
                (commit.tree / str(RECORDS_FILE_RELATIVE)).data_stream.read(),
            )
            for commit in self.__git_repo.iter_commits(paths=str(RECORDS_FILE_RELATIVE))
        )
        prior: dict = {"colrev_status": [], "persisted_IDs": []}
        filecontents = list(revlist)[0][1]
        prior_db_str = io.StringIO(filecontents.decode("utf-8"))
        for record_string in self.__read_next_record_str(file_object=prior_db_str):

            ID, status, origin = "NA", "NA", "NA"
            for line in record_string.split("\n"):
                if "@" in line[:3]:
                    ID = line[line.find("{") + 1 : line.rfind(",")]
                if "colrev_status" == line.lstrip()[:13]:
                    status = line[line.find("{") + 1 : line.rfind("}")]
                if "colrev_origin" == line.strip()[:13]:
                    origin = line[line.find("{") + 1 : line.rfind("}")]
            if "NA" != ID:
                for orig in origin.split(";"):
                    prior["colrev_status"].append([orig, status])
                    if str(RecordState.md_processed) == status:
                        prior["persisted_IDs"].append([orig, ID])

            else:
                logging.error(f"record without ID: {record_string}")

        return prior

    # def read_next_record(file_object) -> typing.Iterator[str]:
    #     data = ""
    #     first_record_processed = False
    #     while True:
    #         line = file_object.readline()
    #         if not line:
    #             break
    #         if line[:1] == "%" or line == "\n":
    #             continue
    #         if line[:1] != "@":
    #             data += line
    #         else:
    #             if first_record_processed:
    #                 yield data
    #             else:
    #                 first_record_processed = True
    #             data = line
    #     yield data

    def retrieve_IDs_from_bib(self, *, file_path: Path) -> list:
        assert file_path.suffix == ".bib"
        IDs = []
        with open(file_path, encoding="utf8") as f:
            line = f.readline()
            while line:
                if "@" in line[:5]:
                    ID = line[line.find("{") + 1 : line.rfind(",")]
                    IDs.append(ID.lstrip())
                line = f.readline()
        return IDs

    def retrieve_by_colrev_id(
        self, *, indexed_record_dict: dict, records: typing.List[typing.Dict]
    ) -> dict:

        INDEXED_RECORD = Record(data=indexed_record_dict)

        if "colrev_id" in INDEXED_RECORD.data:
            cid_to_retrieve = INDEXED_RECORD.get_colrev_id()
        else:
            cid_to_retrieve = [INDEXED_RECORD.create_colrev_id()]

        record_l = [
            x
            for x in records
            if any(cid in Record(data=x).get_colrev_id() for cid in cid_to_retrieve)
        ]
        if len(record_l) != 1:
            raise colrev_exceptions.RecordNotInRepoException
        return record_l[0]

    def update_colrev_ids(self) -> None:

        self.REVIEW_MANAGER.logger.info("Create colrev_id list from origins")
        recs_dict = self.load_records_dict()
        if len(recs_dict) > 0:
            origin_records = self.load_origin_records()
            for rec in tqdm(recs_dict.values()):
                RECORD = Record(data=rec)
                try:
                    colrev_id = RECORD.create_colrev_id()
                    RECORD.data["colrev_id"] = [colrev_id]
                except colrev_exceptions.NotEnoughDataToIdentifyException:
                    continue
                origins = RECORD.get_origins()
                RECORD.add_colrev_ids(
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
            #             RECORD = Record(rec)
            #             HIST_RECORD = Record(hist_rec)
            #             # TODO : acces hist_rec based on an origin-key record-list?
            #             if RECORD.shares_origins(HIST_RECORD):
            #                 RECORD.add_colrev_ids([HIST_RECORD.get_data()])

            self.save_records_dict(records=recs_dict)
            self.add_record_changes()

    def get_missing_files(self) -> list:

        # excluding pdf_not_available
        file_required_status = [
            str(RecordState.pdf_imported),
            str(RecordState.pdf_needs_manual_preparation),
            str(RecordState.pdf_prepared),
            str(RecordState.rev_excluded),
            str(RecordState.rev_included),
            str(RecordState.rev_synthesized),
        ]
        missing_files = []
        if self.REVIEW_MANAGER.paths["RECORDS_FILE"].is_file():
            for record_header_item in self.__read_record_header_items():
                if (
                    record_header_item["colrev_status"] in file_required_status
                    and "NA" == record_header_item["file"]
                ):
                    missing_files.append(record_header_item["ID"])
        return missing_files

    def import_file(self, *, record: dict) -> dict:
        self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"].mkdir(exist_ok=True)
        new_fp = (
            self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]
            / Path(record["ID"] + ".pdf").name
        )
        original_fp = Path(record["file"])

        if "symlink" == self.REVIEW_MANAGER.settings.pdf_get.pdf_path_type:
            if not new_fp.is_file():
                new_fp.symlink_to(original_fp)
            record["file"] = str(new_fp)
        elif "copy" == self.REVIEW_MANAGER.settings.pdf_get.pdf_path_type:
            if not new_fp.is_file():
                shutil.copyfile(original_fp, new_fp.resolve())
            record["file"] = str(new_fp)
        # Note : else: leave absolute paths

        return record

    # CHECKS --------------------------------------------------------------

    def check_main_records_duplicates(self, *, data: dict) -> None:

        if not len(data["IDs"]) == len(set(data["IDs"])):
            duplicates = [ID for ID in data["IDs"] if data["IDs"].count(ID) > 1]
            if len(duplicates) > 20:
                raise colrev_exceptions.DuplicateIDsError(
                    "Duplicates in RECORDS_FILE: "
                    f"({','.join(duplicates[0:20])}, ...)"
                )
            raise colrev_exceptions.DuplicateIDsError(
                f"Duplicates in RECORDS_FILE: {','.join(duplicates)}"
            )

    def check_main_records_origin(self, *, prior: dict, data: dict) -> None:

        # Check whether each record has an origin
        if not len(data["entries_without_origin"]) == 0:
            raise colrev_exceptions.OriginError(
                f"Entries without origin: {', '.join(data['entries_without_origin'])}"
            )

        # Check for broken origins
        search_dir = self.REVIEW_MANAGER.paths["SEARCHDIR"]
        all_record_links = []
        for bib_file in search_dir.glob("*.bib"):
            search_IDs = self.retrieve_IDs_from_bib(file_path=bib_file)
            for x in search_IDs:
                all_record_links.append(bib_file.name + "/" + x)
        delta = set(data["record_links_in_bib"]) - set(all_record_links)
        if len(delta) > 0:
            raise colrev_exceptions.OriginError(f"broken origins: {delta}")

        # Check for non-unique origins
        origins = list(itertools.chain(*data["origin_list"]))
        non_unique_origins = []
        for org in origins:
            if origins.count(org) > 1:
                non_unique_origins.append(org)
        if non_unique_origins:
            for _, org in data["origin_list"]:
                if org in non_unique_origins:
                    raise colrev_exceptions.OriginError(
                        f'Non-unique origin: origin="{org}"'
                    )

        # TODO : Check for removed origins
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
        #                 check_propagated_IDs(prior_id, new_id)
        #                 STATUS = FAIL

    def check_fields(self, *, data: dict) -> None:
        # Check status fields
        status_schema = [str(x) for x in RecordState]
        stat_diff = set(data["status_fields"]).difference(status_schema)
        if stat_diff:
            raise colrev_exceptions.FieldValueError(
                f"status field(s) {stat_diff} not in {status_schema}"
            )

    def check_status_transitions(self, *, data: dict) -> None:
        if len(set(data["start_states"])) > 1:
            raise colrev_exceptions.StatusTransitionError(
                "multiple transitions from different "
                f'start states ({set(data["start_states"])})'
            )
        if len(set(data["invalid_state_transitions"])) > 0:
            raise colrev_exceptions.StatusTransitionError(
                "invalid state transitions: \n    "
                + "\n    ".join(data["invalid_state_transitions"])
            )

    def __get_screening_criteria(self, *, ec_string: str) -> list:
        excl_criteria = [ec.split("=")[0] for ec in ec_string.split(";") if ec != "NA"]
        if [""] == excl_criteria:
            excl_criteria = []
        return excl_criteria

    def check_corrections_of_curated_records(self) -> None:
        from colrev_core.environment import LocalIndex
        from colrev_core.environment import Resources

        if not self.RECORDS_FILE.is_file():
            return

        self.REVIEW_MANAGER.logger.debug("Start corrections")

        self.LOCAL_INDEX = LocalIndex()

        # TODO : remove the following:
        # from colrev_core.prep import Preparation
        # self.PREPARATION = Preparation(
        #     REVIEW_MANAGER=self.REVIEW_MANAGER, notify_state_transition_process=False
        # )

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

        self.REVIEW_MANAGER.logger.debug("Retrieve prior bib")
        RECORDS_FILE_RELATIVE = self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]
        revlist = (
            (
                commit.hexsha,
                (commit.tree / str(RECORDS_FILE_RELATIVE)).data_stream.read(),
            )
            for commit in self.__git_repo.iter_commits(paths=str(RECORDS_FILE_RELATIVE))
        )
        prior: dict = {"curated_records": []}

        try:
            filecontents = list(revlist)[0][1]
        except IndexError:
            return

        self.REVIEW_MANAGER.logger.debug("Load prior bib")
        prior_db_str = io.StringIO(filecontents.decode("utf-8"))
        for record_string in self.__read_next_record_str(file_object=prior_db_str):

            # TBD: whether/how to detect dblp. Previously:
            # if any(x in record_string for x in ["{CURATED:", "{DBLP}"]):
            if "{CURATED:" in record_string:
                records_dict = self.load_records_dict(load_str=record_string)
                r = list(records_dict.values())[0]
                prior["curated_records"].append(r)

        self.REVIEW_MANAGER.logger.debug("Load current bib")
        curated_records = []
        with open(self.RECORDS_FILE, encoding="utf8") as f:
            for record_string in self.__read_next_record_str(file_object=f):

                # TBD: whether/how to detect dblp. Previously:
                # if any(x in record_string for x in ["{CURATED:", "{DBLP}"]):
                if "{CURATED:" in record_string:
                    records_dict = self.load_records_dict(load_str=record_string)
                    r = list(records_dict.values())[0]
                    curated_records.append(r)

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
                self.REVIEW_MANAGER.logger.debug("No prior records found")
                continue

            for prior_cr in prior_crl:

                if not all(
                    prior_cr.get(k, "NA") == curated_record.get(k, "NA")
                    for k in essential_md_keys
                ):
                    # after the previous condition, we know that the curated record
                    # has been corrected
                    corrected_curated_record = curated_record.copy()
                    if Record(data=corrected_curated_record).masterdata_is_curated():
                        # retrieve record from index to identify origin repositories
                        try:
                            original_curated_record = self.LOCAL_INDEX.retrieve(
                                record=prior_cr
                            )

                            # Note : this is a simple heuristic:
                            curation_path = Resources.curations_path / Path(
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

                        original_curated_record["colrev_id"] = Record(
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
                    fp = self.REVIEW_MANAGER.paths["CORRECTIONS_PATH"] / Path(
                        f"{curated_record['ID']}.json"
                    )
                    fp.parent.mkdir(exist_ok=True)

                    with open(fp, "w", encoding="utf8") as corrections_file:
                        json.dump(dict_to_save, corrections_file, indent=4)

                    # TODO : combine merge-record corrections

        # for testing:
        # raise KeyError

    def check_main_records_screen(self, *, data: dict) -> None:

        # Check screen
        # Note: consistency of inclusion_2=yes -> inclusion_1=yes
        # is implicitly ensured through status
        # (screen2-included/excluded implies prescreen included!)

        field_errors = []

        if data["screening_criteria_list"]:
            screening_criteria = data["screening_criteria_list"][0][2]
            if screening_criteria != "NA":
                criteria = self.__get_screening_criteria(ec_string=screening_criteria)
                settings_criteria = list(
                    self.REVIEW_MANAGER.settings.screen.criteria.keys()
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
            for [ID, status, excl_crit] in data["screening_criteria_list"]:
                # print([ID, status, excl_crit])
                if not re.match(pattern, excl_crit):
                    # Note: this should also catch cases of missing
                    # screening criteria
                    field_errors.append(
                        "Screening criteria field not matching "
                        f"pattern: {excl_crit} ({ID}; criteria: {criteria})"
                    )

                elif str(RecordState.rev_excluded) == status:
                    if ["NA"] == criteria:
                        if "NA" == excl_crit:
                            continue
                        field_errors.append(f"excl_crit field not NA: {excl_crit}")

                    if "=out" not in excl_crit:
                        logging.error(f"criteria: {criteria}")
                        field_errors.append(
                            "Excluded record with no screening_criterion violated: "
                            f"{ID}, {status}, {excl_crit}"
                        )

                # Note: we don't have to consider the cases of
                # status=retrieved/prescreen_included/prescreen_excluded
                # because they would not have screening_criteria.
                elif status in [
                    str(RecordState.rev_included),
                    str(RecordState.rev_synthesized),
                ]:
                    if not re.match(pattern_inclusion, excl_crit):
                        field_errors.append(
                            "Included record with screening_criterion satisfied: "
                            f"{ID}, {status}, {excl_crit}"
                        )
                else:
                    if not re.match(pattern_inclusion, excl_crit):
                        field_errors.append(
                            "Record with screening_criterion but before "
                            f"screen: {ID}, {status}"
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

    def check_propagated_IDs(self, *, prior_id: str, new_id: str) -> list:

        ignore_patterns = [
            ".git",
            "report.log",
            ".pre-commit-config.yaml",
        ]

        text_formats = [".txt", ".csv", ".md", ".bib", ".yaml"]
        notifications = []
        for root, dirs, files in os.walk(self.REVIEW_MANAGER.path, topdown=False):
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
                    retrieved_IDs = self.retrieve_IDs_from_bib(
                        file_path=Path(os.path.join(root, name))
                    )
                    if prior_id in retrieved_IDs:
                        msg = (
                            f"Old ID ({prior_id}, changed to {new_id} in "
                            + f"the RECORDS_FILE) found in file: {name}"
                        )
                        if msg not in notifications:
                            notifications.append(msg)
                else:
                    with open(os.path.join(root, name), encoding="utf8") as f:
                        line = f.readline()
                        while line:
                            if name.endswith(".bib") and "@" in line[:5]:
                                line = f.readline()
                            if prior_id in line:
                                msg = (
                                    f"Old ID ({prior_id}, to {new_id} in "
                                    + f"the RECORDS_FILE) found in file: {name}"
                                )
                                if msg not in notifications:
                                    notifications.append(msg)
                            line = f.readline()
            for name in dirs:
                if any((x in name) or (x in root) for x in ignore_patterns):
                    continue
                if prior_id in name:
                    notifications.append(
                        f"Old ID ({prior_id}, changed to {new_id} in the "
                        f"RECORDS_FILE) found in filepath: {name}"
                    )
        return notifications

    def check_persisted_ID_changes(self, *, prior: dict, data: dict) -> None:
        if "persisted_IDs" not in prior:
            return
        for prior_origin, prior_id in prior["persisted_IDs"]:
            if prior_origin not in [x[0] for x in data["persisted_IDs"]]:
                # Note: this does not catch origins removed before md_processed
                raise colrev_exceptions.OriginError(f"origin removed: {prior_origin}")
            for new_origin, new_id in data["persisted_IDs"]:
                if new_origin == prior_origin:
                    if new_id != prior_id:
                        notifications = self.check_propagated_IDs(
                            prior_id=prior_id, new_id=new_id
                        )
                        notifications.append(
                            "ID of processed record changed from "
                            f"{prior_id} to {new_id}"
                        )
                        raise colrev_exceptions.PropagatedIDChange(notifications)

    def check_sources(self) -> None:

        SOURCES = self.REVIEW_MANAGER.settings.sources

        for SOURCE in SOURCES:

            if not SOURCE.filename.is_file():
                self.REVIEW_MANAGER.logger.debug(
                    f"Search details without file: {SOURCE.filename}"
                )
                # raise SearchSettingsError('File not found: "
                #                       f"{SOURCE["filename"]}')
            if str(SOURCE.search_type) not in SearchType._member_names_:
                raise colrev_exceptions.SearchSettingsError(
                    f"{SOURCE.search_type} not in {SearchType._member_names_}"
                )

            # date_regex = r"^\d{4}-\d{2}-\d{2}$"
            # if "completion_date" in SOURCE:
            #     if not re.search(date_regex, SOURCE["completion_date"]):
            #         raise SearchSettingsError(
            #             "completion date not matching YYYY-MM-DD format: "
            #             f'{SOURCE["completion_date"]}'
            #         )
            # if "start_date" in SOURCE:
            #     if not re.search(date_regex, SOURCE["start_date"]):
            #         raise SearchSettingsError(
            #             "start_date date not matchin YYYY-MM-DD format: "
            #             f'{SOURCE["start_date"]}'
            #         )

    # GIT operations -----------------------------------------------

    def get_repo(self) -> git.Repo:
        """Get the git repository object (requires REVIEW_MANAGER.notify(...))"""

        if self.REVIEW_MANAGER.notified_next_process is None:
            raise colrev_exceptions.ReviewManagerNotNofiedError()
        return self.__git_repo

    def has_changes(self) -> bool:
        # Extension : allow for optional path (check changes for that file)
        return self.__git_repo.is_dirty()

    def add_changes(self, *, path: str) -> None:

        while (self.REVIEW_MANAGER.path / Path(".git/index.lock")).is_file():
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

        while (self.REVIEW_MANAGER.path / Path(".git/index.lock")).is_file():
            time.sleep(0.5)
            print("Waiting for previous git operation to complete")
        self.__git_repo.index.add(
            [str(self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"])]
        )

    def add_setting_changes(self) -> None:

        while (self.REVIEW_MANAGER.path / Path(".git/index.lock")).is_file():
            time.sleep(0.5)
            print("Waiting for previous git operation to complete")

        self.__git_repo.index.add([str(self.REVIEW_MANAGER.paths["SETTINGS_RELATIVE"])])

    def reset_log_if_no_changes(self) -> None:
        if not self.__git_repo.is_dirty():
            self.REVIEW_MANAGER.reset_log()

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
            self.REVIEW_MANAGER.logger.debug(f"{branch_name} - {tracking_branch_name}")

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = self.__git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = self.__git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

        return [nr_commits_behind, nr_commits_ahead]

    def behind_remote(self) -> bool:
        nr_commits_behind = 0
        CONNECTED_REMOTE = 0 != len(self.__git_repo.remotes)
        if CONNECTED_REMOTE:
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
        CONNECTED_REMOTE = 0 != len(self.__git_repo.remotes)
        if CONNECTED_REMOTE:
            origin = self.__git_repo.remotes.origin
            if origin.exists():
                (
                    _,
                    nr_commits_ahead,
                ) = self.get_remote_commit_differences()
        if nr_commits_ahead > 0:
            return True
        return False

    def pull_if_repo_clean(self):
        if not self.__git_repo.is_dirty():
            o = self.__git_repo.remotes.origin
            o.pull()


if __name__ == "__main__":
    pass
