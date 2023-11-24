#! /usr/bin/env python
"""Convenience functions to load bib files

Usage::

    import colrev.ops.load_utils_bib

    records = colrev.ops.load_utils_bib.load_bib_file(
        load_operation=load_operation, source=self.search_source
    )

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

import os
import re
import typing
from typing import TYPE_CHECKING

import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.load


def __apply_file_fixes(
    *,
    load_operation: colrev.ops.load.Load,
    source: colrev.settings.SearchSource,
) -> None:
    # pylint: disable=duplicate-code
    # pylint: disable=too-many-statements

    def fix_key(
        file: typing.IO, line: bytes, replacement_line: bytes, seekpos: int
    ) -> int:
        load_operation.review_manager.logger.info(
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

    if not source.filename.is_file():
        load_operation.review_manager.logger.debug(
            f"Did not find bib file {source.filename} "
        )
        return

    with open(source.filename, encoding="utf8") as bibtex_file:
        contents = bibtex_file.read()
        bib_r = re.compile(r"@.*{.*,", re.M)
        if len(re.findall(bib_r, contents)) == 0:
            load_operation.review_manager.logger.error(
                f"Not a bib file? {source.filename.name}"
            )
            raise colrev_exceptions.UnsupportedImportFormatError(source.filename)

    # Errors to fix before pybtex loading:
    # - set_incremental_ids (otherwise, not all records will be loaded)
    # - fix_keys (keys containing white spaces)
    record_ids: typing.List[str] = []
    with open(source.filename, "r+b") as file:
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
                    next_id = (
                        load_operation.review_manager.dataset.generate_next_unique_id(
                            temp_id=current_id_str, existing_ids=record_ids
                        )
                    )
                    load_operation.review_manager.logger.info(
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
            if re.match(r"^\s*[a-zA-Z0-9]+\s+[a-zA-Z0-9]+\s*\=", line.decode("utf-8")):
                replacement_line = re.sub(
                    r"(^\s*)([a-zA-Z0-9]+)\s+([a-zA-Z0-9]+)(\s*\=)",
                    r"\1\2_\3\4",
                    line.decode("utf-8"),
                ).encode("utf-8")
                seekpos = fix_key(file, line, replacement_line, seekpos)

            seekpos = file.tell()
            line = file.readline()


def load_bib_file(
    load_operation: colrev.ops.load.Load,
    source: colrev.settings.SearchSource,
    check_bib_file: bool = True,
) -> dict:
    """Load a bib file and return records dict"""

    # TODO (Tarin): create class (which handles the load_operation) and extract the following functions

    def drop_empty_fields(*, records: dict) -> None:
        for record_id in records:
            records[record_id] = {
                k: v for k, v in records[record_id].items() if v is not None
            }
            records[record_id] = {
                k: v for k, v in records[record_id].items() if v != "nan"
            }

    def check_nr_in_bib(*, source: colrev.settings.SearchSource, records: dict) -> None:
        load_operation.review_manager.logger.debug(
            f"Loaded {source.filename.name} with {len(records)} records"
        )
        nr_in_bib = load_operation.review_manager.dataset.get_nr_in_bib(
            file_path=source.filename
        )
        if len(records) < nr_in_bib:
            load_operation.review_manager.logger.error(
                "broken bib file (not imported all records)"
            )
            with open(source.filename, encoding="utf8") as file:
                line = file.readline()
                while line:
                    if "@" in line[:3]:
                        record_id = line[line.find("{") + 1 : line.rfind(",")]
                        if record_id not in [x[Fields.ID] for x in records.values()]:
                            load_operation.review_manager.logger.error(
                                f"{record_id} not imported"
                            )
                    line = file.readline()

    def __check_bib_file(
        *, source: colrev.settings.SearchSource, records: dict
    ) -> None:
        if len(records.items()) <= 3:
            return
        if not any(Fields.AUTHOR in r for r in records.values()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with author field): {source.filename.name}"
            )

        if not any(Fields.TITLE in r for ID, r in records.items()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with title field): {source.filename.name}"
            )

    def __load_records(*, source: colrev.settings.SearchSource) -> dict:
        if not source.filename.is_file():
            return {}
        with open(source.filename, encoding="utf8") as bibtex_file:
            records = load_operation.review_manager.dataset.load_records_dict(
                load_str=bibtex_file.read()
            )

            if len(records) == 0:
                load_operation.review_manager.report_logger.debug("No records loaded")
                load_operation.review_manager.logger.debug("No records loaded")
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
                    f"not found in {source.filename.name}"
                )
                continue
            crossref_ids.append(crossref_record["ID"])
            for key, value in crossref_record.items():
                if key not in record_dict:
                    record_dict[key] = value
            del record_dict["crossref"]

        for crossref_id in crossref_ids:
            del records[crossref_id]

    __apply_file_fixes(load_operation=load_operation, source=source)

    records = __load_records(source=source)
    if len(records) == 0:
        return records

    lower_case_keys(records=records)
    drop_empty_fields(records=records)
    resolve_crossref(records=records)
    records = dict(sorted(records.items()))
    check_nr_in_bib(source=source, records=records)
    if check_bib_file:
        __check_bib_file(source=source, records=records)
    return records


class BIBLoader:
    """Loads bib files"""

    __current_source: typing.TextIO

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        list_fields: dict,
        unique_id_field: str = "",
    ):
        self.load_operation = load_operation
        self.source = source
        self.unique_id_field = unique_id_field

        self.__current_record: dict = {}
        self.list_fields = list_fields

    def __check_source_file(self) -> None:
        if not self.source.filename.is_file():
            exp = colrev_exceptions.UnsupportedImportFormatError(self.source.filename)
            self.load_operation.review_manager.logger.debug(exp.message)
            raise exp

    def __apply_file_fixes(self) -> None:
        # pylint: disable=duplicate-code
        # pylint: disable=too-many-statements
        self.__check_source_file()

        contents = self.__read_current_file()
        bib_r = re.compile(r"@.*{.*,", re.M)
        if len(re.findall(bib_r, contents)) == 0:
            exp = colrev_exceptions.UnsupportedImportFormatError(self.source.filename)
            self.load_operation.review_manager.logger.error(exp.message)
            raise exp

        # Errors to fix before pybtex loading:
        # - set_incremental_ids (otherwise, not all records will be loaded)
        # - fix_keys (keys containing white spaces)
        record_ids: typing.List[str] = []
        with open(self.source.filename, "r+b") as file:
            generate_next_unique_id = (
                self.load_operation.review_manager.dataset.generate_next_unique_id
            )
            seek_pos = file.tell()
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
                        seek_pos = self.__fix_key(
                            file, line, replacement_line, seek_pos
                        )

                    if current_id_str in record_ids:
                        next_id = generate_next_unique_id(
                            temp_id=current_id_str, existing_ids=record_ids
                        )
                        self.load_operation.review_manager.logger.info(
                            f"Fix duplicate ID: {current_id_str} >> {next_id}"
                        )

                        replacement_line = (
                            line.decode("utf-8")
                            .replace(current_id.decode("utf-8"), next_id)
                            .encode("utf-8")
                        )

                        seek_pos = self.__fix_key(
                            file, line, replacement_line, seek_pos
                        )
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
                    self.__fix_key(file, line, replacement_line, seek_pos)

                seek_pos = file.tell()
                line = file.readline()

    def __fix_key(
        self, file: typing.IO, line: bytes, replacement_line: bytes, seek_pos: int
    ) -> int:
        self.load_operation.review_manager.logger.info(
            f"Fix invalid key: \n{line.decode('utf-8')}"
            f"{replacement_line.decode('utf-8')}"
        )
        line = file.readline()
        remaining = line + file.read()
        file.seek(seek_pos)
        file.write(replacement_line)
        seek_pos = file.tell()
        file.flush()
        os.fsync(file)
        file.write(remaining)
        file.truncate()  # if the replacement is shorter...
        file.seek(seek_pos)
        return seek_pos

    def __read_current_file(self) -> str:
        """Reads current file and returns content"""
        content = self.__current_file().read()
        self.__current_file().seek(os.SEEK_SET)
        return content

    def __current_file(self) -> typing.TextIO:
        if self.__current_source:
            self.__current_source.seek(os.SEEK_SET)
            return self.__current_source
        raise colrev_exceptions.ImportException(
            f"File is not loaded: {self.source.filename}"
        )

    def __drop_empty_fields(self) -> None:
        """Clear empty columns"""
        fields = dict(self.__current_record)
        for k, field in fields.items():
            if not field or field == "nan":
                del self.__current_record[k]

    def __check_nr_in_bib(self, *, records: dict) -> None:
        self.load_operation.review_manager.logger.debug(
            f"Loaded {self.source.filename.name} with {len(records)} records"
        )

        file = self.__current_file()
        if not file:
            raise colrev_exceptions.ImportException("No file provided")
        nr_in_bib = self.load_operation.review_manager.dataset.get_nr_in_bib(
            file_path=self.source.filename
        )
        if len(records) < nr_in_bib:
            self.load_operation.review_manager.logger.error(
                "broken bib file (not imported all records)"
            )
            file.seek(os.SEEK_SET)
            line = file.readline()
            while line:
                if "@" in line[:3]:
                    record_id = line[line.find("{") + 1 : line.rfind(",")]
                    if record_id not in [x[Fields.ID] for x in records.values()]:
                        self.load_operation.review_manager.logger.error(
                            f"{record_id} not imported"
                        )
                line = file.readline()

    def __check_bib_file(self, *, records: dict) -> None:
        if len(records.items()) <= 3:
            return
        if not any(Fields.AUTHOR in r for r in records.values()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with author field): {self.source.filename.name}"
            )

        if not any(Fields.TITLE in r for ID, r in records.items()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with title field): {self.source.filename.name}"
            )

    def __load_records(self) -> dict:
        records = self.load_operation.review_manager.dataset.load_records_dict(
            load_str=self.__read_current_file()
        )

        if len(records) == 0:
            self.load_operation.review_manager.report_logger.debug("No records loaded")
            self.load_operation.review_manager.logger.debug("No records loaded")
        return records

    def __lower_case_keys(self) -> None:
        for key in list(self.__current_record.keys()):
            if key in [Fields.ID, Fields.ENTRYTYPE]:
                continue
            if not key.islower():
                self.__current_record[key.lower()] = self.__current_record.pop(key)

    def __resolve_crossref(self, *, records: dict) -> None:
        # https://bibtex.eu/fields/crossref/
        crossref_ids = []
        for record_dict in records.values():
            if "crossref" not in record_dict:
                continue

            crossref_record = records[record_dict["crossref"]]

            if not crossref_record:
                print(
                    f"crossref record (ID={record_dict['crossref']}) "
                    f"not found in {self.source.filename.name}"
                )
                continue
            crossref_ids.append(crossref_record["ID"])
            for key, value in crossref_record.items():
                if key not in record_dict:
                    record_dict[key] = value
            del record_dict["crossref"]

        for crossref_id in crossref_ids:
            del records[crossref_id]

    def load_bib_file(
        self,
        *,
        check_bib_file: bool = True,
    ) -> dict:
        """Load a bib file and return records dict"""

        with open(self.source.filename, encoding="utf-8") as file:
            self.__current_source = file
            try:
                self.__apply_file_fixes()
            except colrev_exceptions.UnsupportedImportFormatError:
                return {}
            records = self.__load_records()
            if len(records) == 0:
                return records
            for _record_id, record in records.items():
                self.__current_record = record
                self.__lower_case_keys()
                self.__drop_empty_fields()
            self.__check_nr_in_bib(records=records)
            self.__resolve_crossref(records=records)
            records = dict(sorted(records.items()))
            if check_bib_file:
                self.__check_bib_file(records=records)
            return records
