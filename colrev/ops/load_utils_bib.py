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
                        if record_id not in [x[Fields.ID] for x in records]:
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

    __apply_file_fixes(load_operation=load_operation, source=source)

    records = __load_records(source=source)
    if len(records) == 0:
        return records

    lower_case_keys(records=records)
    drop_empty_fields(records=records)
    records = dict(sorted(records.items()))
    check_nr_in_bib(source=source, records=records)
    if check_bib_file:
        __check_bib_file(source=source, records=records)
    return records
