#! /usr/bin/env python
"""Convenience functions to load bib files"""
from __future__ import annotations

import io
import itertools
import logging
import os
import re
import string
import typing
from pathlib import Path

import pybtex.errors
from pybtex.database import Person
from pybtex.database.input import bibtex

import colrev.exceptions as colrev_exceptions
import colrev.loader.loader
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import FieldValues
from colrev.constants import RecordState


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments


class BIBLoader(colrev.loader.loader.Loader):
    """Loads BibTeX files"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        filename: Path,
        unique_id_field: str = "ID",
        entrytype_setter: typing.Callable = lambda x: x,
        field_mapper: typing.Callable = lambda x: x,
        id_labeler: typing.Callable = lambda x: x,
        logger: logging.Logger = logging.getLogger(__name__),
    ):
        super().__init__(
            filename=filename,
            id_labeler=id_labeler,
            unique_id_field=unique_id_field,
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
        )

    @classmethod
    def get_nr_records(cls, filename: Path) -> int:
        """Get the number of records in the file"""
        count = 0
        with open(filename, encoding="utf8") as file:
            for line in file:
                if line.startswith("@") and "@comment" not in line[:10].lower():
                    count += 1
        return count

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

    def _apply_file_fixes(self) -> None:
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

        if self.filename is not None:

            with open(self.filename, encoding="utf8") as bibtex_file:
                contents = bibtex_file.read()
                if len(contents) < 10:
                    return
                bib_r = re.compile(r"@.*{.*,", re.M)
                if len(re.findall(bib_r, contents)) == 0:
                    self.logger.error(f"Not a bib file? {self.filename.name}")
                    raise colrev_exceptions.UnsupportedImportFormatError(self.filename)

            # Errors to fix before pybtex loading:
            # - set_incremental_ids (otherwise, not all records will be loaded)
            # - fix_keys (keys containing white spaces)
            record_ids: typing.List[str] = []
            with open(self.filename, "r+b") as file:
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
                            next_id = self._generate_next_unique_id(
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

                    # Fix IDs
                    if re.match(
                        r"^@[a-zA-Z0-9]+\{[a-zA-Z0-9]+\s[a-zA-Z0-9]+,",
                        line.decode("utf-8"),
                    ):
                        replacement_line = re.sub(
                            r"^(@[a-zA-Z0-9]+\{[a-zA-Z0-9]+)\s([a-zA-Z0-9]+,)",
                            r"\1_\2",
                            line.decode("utf-8"),
                        ).encode("utf-8")
                        seekpos = fix_key(file, line, replacement_line, seekpos)

                    seekpos = file.tell()
                    line = file.readline()

    def _parse_records_dict(self, *, records_dict: dict) -> dict:
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
                            RecordState[v]
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
                                        if k in FieldSet.LIST_FIELDS
                                        else (
                                            self._load_field_dict(value=v, field=k)
                                            if k in [Fields.MD_PROV, Fields.D_PROV]
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

        return_dict: typing.Dict[str, typing.Any] = {}
        if value == "":  # pragma: no cover
            return return_dict

        if field == Fields.MD_PROV:
            if value[:7] == FieldValues.CURATED:
                source = value[value.find(":") + 1 : value[:-1].rfind(";")]
                return_dict[FieldValues.CURATED] = {
                    "source": source,
                    "note": "",
                }

            else:
                # Pybtex automatically replaces \n in fields.
                # For consistency, we also do that for header_only mode:
                if "\n" in value:  # pragma: no cover
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
            # Note : pybtex replaces \n upon load
            for item in (value + " ").split("; "):
                if item == "":
                    continue
                item += ";"  # removed by split
                key_source = item[: item[:-1].rfind(";")]
                note = item[item[:-1].rfind(";") + 1 : -1]
                assert ":" in key_source, f"problem with data_provenance_item {item}"
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
            return key, RecordState[value]
        if key == Fields.MD_PROV:
            return key, self._load_field_dict(value=value, field=key)
        if key == Fields.FILE:
            return key, Path(value)

        return key, value

    # pylint: disable=too-many-branches
    def _read_record_header_items(
        self, *, file_object: typing.Optional[typing.TextIO] = None
    ) -> list:
        # Note : more than 10x faster than the pybtex part of load_records_dict()

        if file_object is None:
            assert self.filename is not None
            # pylint: disable=consider-using-with
            file_object = open(self.filename, encoding="utf-8")

        # Fields required
        default = {
            Fields.ID: "NA",
            Fields.ORIGIN: "NA",
            Fields.STATUS: "NA",
            Fields.FILE: "NA",
            Fields.SCREENING_CRITERIA: "NA",
            Fields.MD_PROV: "NA",
        }
        # number_required_header_items = len(default)

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

            # if item_count > number_required_header_items or "}" == line:
            #     record_header_items.append(record_header_item)
            #     record_header_item = default.copy()
            #     item_count = 0
            #     continue

            if "@" in line[:2] and record_header_item[Fields.ID] != "NA":
                record_header_items.append(record_header_item)
                record_header_item = default.copy()
                item_count = 0

            item_string += line
            if "}," in line or "@" in line[:2]:
                key, value = self._parse_k_v(item_string)
                # if key == Fields.MD_PROV:
                #     if value == "NA":
                #         value = {}
                # if value == "NA":
                #     item_string = ""
                #     continue
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

    def get_record_header_items(self) -> dict:
        """Get the record header items"""
        record_header_list = []
        record_header_list = self._read_record_header_items()

        record_header_dict = {r[Fields.ID]: r for r in record_header_list}
        return record_header_dict

    def load_records_list(self) -> list:

        def drop_empty_fields(*, records: dict) -> None:
            for record_id in records:
                records[record_id] = {
                    k: v
                    for k, v in records[record_id].items()
                    if v is not None and v != "nan"
                }

        def resolve_crossref(*, records: dict) -> None:
            # https://bibtex.eu/fields/crossref/
            crossref_ids = []
            for record_dict in records.values():
                if "crossref" not in record_dict:
                    continue

                crossref_record = records.get(record_dict["crossref"], None)

                if not crossref_record:
                    self.logger.error(
                        f"crossref record (ID={record_dict['crossref']}) not found"
                    )
                    continue
                crossref_ids.append(crossref_record["ID"])
                for key, value in crossref_record.items():
                    if key not in record_dict:
                        record_dict[key] = value
                del record_dict["crossref"]

            for crossref_id in crossref_ids:
                del records[crossref_id]

        self._apply_file_fixes()

        temp_f = io.StringIO()
        pybtex.io.stderr = temp_f
        pybtex.errors.set_strict_mode(False)
        parser = bibtex.Parser()
        bib_data = parser.parse_file(str(self.filename))
        records = self._parse_records_dict(records_dict=bib_data.entries)

        drop_empty_fields(records=records)
        resolve_crossref(records=records)
        records = dict(sorted(records.items()))

        return list(records.values())
