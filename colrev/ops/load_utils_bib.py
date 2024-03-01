#! /usr/bin/env python
"""Convenience functions to load bib files

Usage::

    import colrev.ops.load_utils_bib

    bib_loader = colrev.ops.load_utils_bib.BIBLoader(
        source_file=self.search_source.filename,
        logger=load_operation.review_manager.logger,
        force_mode=load_operation.review_manager.force_mode,
    )
    records = bib_loader.load_bib_file()

    Example BibTeX record::

    @article{Guo2021,
        title    = {How Trust Leads to Commitment on Microsourcing Platforms},
        author   = {Guo, Wenbo and Straub, Detmar W. and Zhang, Pengzhu and Cai, Zhao},
        journal  = {MIS Quarterly},
        year     = {2021}
        volume   = {45},
        number   = {3},
        pages    = {1309--1348},
        url      = {https://aisel.aisnet.org/misq/vol45/iss3/13},
        doi      = {10.25300/MISQ/2021/16100},
    }

"""
from __future__ import annotations

import itertools
import logging
import os
import re
import string
import typing
from pathlib import Path

from pybtex.database import Person
from pybtex.database.input import bibtex

import colrev.exceptions as colrev_exceptions
import colrev.record
from colrev.constants import Fields
from colrev.constants import FieldValues


# pylint: disable=too-few-public-methods


class BIBLoader:
    """Loads BibTeX files"""

    def __init__(
        self,
        *,
        source_file: Path,
        unique_id_field: str = "",
        logger: logging.Logger,
        force_mode: bool = False,
    ):

        if not source_file.name.endswith(".bib"):
            raise colrev_exceptions.ImportException(
                f"File not supported by BIBLoader: {source_file.name}"
            )
        if not source_file.exists():
            raise colrev_exceptions.ImportException(
                f"File not found: {source_file.name}"
            )

        self.unique_id_field = unique_id_field
        self.logger = logger
        self.force_mode = force_mode
        self.source_file = source_file

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

    def _apply_file_fixes(self) -> None:
        # pylint: disable=duplicate-code
        # pylint: disable=too-many-statements

        def fix_key(
            file: typing.IO, line: bytes, replacement_line: bytes, seekpos: int
        ) -> int:
            self.logger.info(
                f"Fix invalid key: \n{line.decode('utf-8')}"
                f"{replacement_line.decode('utf-8')}"
            )
            line = file.readline()
            remaining = line + file.read()
            file.seek(seekpos)
            file.write(replacement_line)
            seekpos = file.tell()
            file.flush()
            os.fsync(file)
            file.write(remaining)
            file.truncate()  # if the replacement is shorter...
            file.seek(seekpos)
            return seekpos

        with open(self.source_file, encoding="utf8") as bibtex_file:
            contents = bibtex_file.read()
            bib_r = re.compile(r"@.*{.*,", re.M)
            if len(re.findall(bib_r, contents)) == 0:
                self.logger.error(f"Not a bib file? {self.source_file.name}")
                raise colrev_exceptions.UnsupportedImportFormatError(self.source_file)

        # Errors to fix before pybtex loading:
        # - set_incremental_ids (otherwise, not all records will be loaded)
        # - fix_keys (keys containing white spaces)
        record_ids: typing.List[str] = []
        with open(self.source_file, "r+b") as file:
            seekpos = file.tell()
            line = file.readline()
            while line:
                if b"@" in line[:3]:
                    current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                    current_id_str = current_id.decode("utf-8").lstrip().rstrip()

                    if any(x in current_id_str for x in [";"]):
                        replacement_line = re.sub(
                            r";",
                            r"_",
                            line.decode("utf-8"),
                        ).encode("utf-8")
                        seekpos = fix_key(file, line, replacement_line, seekpos)

                    if current_id_str in record_ids:
                        next_id = self.generate_next_unique_id(
                            temp_id=current_id_str, existing_ids=record_ids
                        )
                        self.logger.info(
                            f"Fix duplicate ID: {current_id_str} >> {next_id}"
                        )

                        replacement_line = (
                            line.decode("utf-8")
                            .replace(current_id.decode("utf-8"), next_id)
                            .encode("utf-8")
                        )

                        line = file.readline()
                        remaining = line + file.read()
                        file.seek(seekpos)
                        file.write(replacement_line)
                        seekpos = file.tell()
                        file.flush()
                        os.fsync(file)
                        file.write(remaining)
                        file.truncate()  # if the replacement is shorter...
                        file.seek(seekpos)

                        record_ids.append(next_id)

                    else:
                        record_ids.append(current_id_str)

                # Fix keys
                if re.match(
                    r"^\s*[a-zA-Z0-9]+\s+[a-zA-Z0-9]+\s*\=", line.decode("utf-8")
                ):
                    replacement_line = re.sub(
                        r"(^\s*)([a-zA-Z0-9]+)\s+([a-zA-Z0-9]+)(\s*\=)",
                        r"\1\2_\3\4",
                        line.decode("utf-8"),
                    ).encode("utf-8")
                    seekpos = fix_key(file, line, replacement_line, seekpos)

                seekpos = file.tell()
                line = file.readline()

    def parse_records_dict(self, *, records_dict: dict) -> dict:
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
                **{Fields.ID: k},
                **{Fields.ENTRYTYPE: v.type},
                **dict(
                    {
                        # Cast status to Enum
                        k: (
                            colrev.record.RecordState[v]
                            if (Fields.STATUS == k)
                            # DOIs are case insensitive -> use upper case.
                            else (
                                v.upper()
                                if (Fields.DOI == k)
                                # Note : the following two lines are a temporary fix
                                # to converg colrev_origins to list items
                                else (
                                    [
                                        el.rstrip().lstrip()
                                        for el in v.split(";")
                                        if "" != el
                                    ]
                                    if k == Fields.ORIGIN
                                    else (
                                        [
                                            el.rstrip()
                                            for el in (v + " ").split("; ")
                                            if "" != el
                                        ]
                                        if k in colrev.record.Record.list_fields_keys
                                        else (
                                            self._load_field_dict(value=v, field=k)
                                            if k
                                            in colrev.record.Record.dict_fields_keys
                                            else v
                                        )
                                    )
                                )
                            )
                        )
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

    def _load_field_dict(self, *, value: str, field: str) -> dict:
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

    def load_bib_file(
        self,
        check_bib_file: bool = True,
    ) -> dict:
        """Load a bib file and return records dict"""

        def drop_empty_fields(*, records: dict) -> None:
            for record_id in records:
                records[record_id] = {
                    k: v for k, v in records[record_id].items() if v is not None
                }
                records[record_id] = {
                    k: v for k, v in records[record_id].items() if v != "nan"
                }

        # def check_nr_in_bib(*, records: dict) -> None:
        #     self.logger.debug(
        #         f"Loaded {self.source_file.name} with {len(records)} records"
        #     )
        #     nr_in_bib = self.review_manager.dataset.get_nr_in_bib(
        #         file_path=self.source_file
        #     )
        #     if len(records) < nr_in_bib:
        #         self.logger.error("broken bib file (not imported all records)")
        #         with open(self.source_file, encoding="utf8") as file:
        #             line = file.readline()
        #             while line:
        #                 if "@" in line[:3]:
        #                     record_id = line[line.find("{") + 1 : line.rfind(",")]
        #                     if record_id not in [
        #                         x[Fields.ID] for x in records.values()
        #                     ]:
        #                         self.review_manager.logger.error(
        #                             f"{record_id} not imported"
        #                         )
        #                 line = file.readline()

        def _load_records() -> dict:
            if not self.source_file.is_file():
                return {}
            parser = bibtex.Parser()
            bib_data = parser.parse_file(str(self.source_file))
            records = self.parse_records_dict(records_dict=bib_data.entries)

            if len(records) == 0:
                self.logger.debug("No records loaded")
            return records

        def lower_case_keys(*, records: dict) -> None:
            for record in records.values():
                for key in list(record.keys()):
                    if key in [Fields.ID, Fields.ENTRYTYPE]:
                        continue
                    if not key.islower():
                        record[key.lower()] = record.pop(key)

        def resolve_crossref(*, records: dict) -> None:
            # https://bibtex.eu/fields/crossref/
            crossref_ids = []
            for record_dict in records.values():
                if "crossref" not in record_dict:
                    continue

                crossref_record = records[record_dict["crossref"]]

                if not crossref_record:
                    print(
                        f"crossref record (ID={record_dict['crossref']}) "
                        f"not found in {self.source_file.name}"
                    )
                    continue
                crossref_ids.append(crossref_record["ID"])
                for key, value in crossref_record.items():
                    if key not in record_dict:
                        record_dict[key] = value
                del record_dict["crossref"]

            for crossref_id in crossref_ids:
                del records[crossref_id]

        if not check_bib_file:
            records = _load_records()
            return records

        self._apply_file_fixes()
        records = _load_records()
        lower_case_keys(records=records)
        drop_empty_fields(records=records)
        resolve_crossref(records=records)
        records = dict(sorted(records.items()))
        # TODO : temporarily deactivated
        # check_nr_in_bib(records=records)

        return records
