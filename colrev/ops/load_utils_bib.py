#! /usr/bin/env python
"""Convenience functions to load bib files"""
from __future__ import annotations

import os
import re
import typing
from pathlib import Path
from typing import TYPE_CHECKING

import colrev.exceptions as colrev_exceptions

if TYPE_CHECKING:
    import colrev.ops.load


def __apply_file_fixes(*, load_operation: colrev.ops.load.Load, filename: Path) -> None:
    # pylint: disable=duplicate-code

    if not filename.is_file():
        return

    # Errors to fix before pybtex loading:
    # - set_incremental_ids (otherwise, not all records will be loaded)
    # - fix_keys (keys containing white spaces)
    record_ids: typing.List[str] = []
    with open(filename, "r+b") as file:
        seekpos = file.tell()
        line = file.readline()
        while line:
            if b"@" in line[:3]:
                current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                current_id_str = current_id.decode("utf-8").lstrip().rstrip()

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

            seekpos = file.tell()
            line = file.readline()


def load_bib_file(
    load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
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
        nr_in_bib = load_operation.review_manager.dataset.get_nr_in_bib(
            file_path=source.get_corresponding_bib_file()
        )
        if len(records) < nr_in_bib:
            load_operation.review_manager.logger.error(
                "broken bib file (not imported all records)"
            )
            with open(source.get_corresponding_bib_file(), encoding="utf8") as file:
                line = file.readline()
                while line:
                    if "@" in line[:3]:
                        record_id = line[line.find("{") + 1 : line.rfind(",")]
                        if record_id not in [x["ID"] for x in records]:
                            load_operation.review_manager.logger.error(
                                f"{record_id} not imported"
                            )
                    line = file.readline()

    def check_bib_file(*, source: colrev.settings.SearchSource, records: dict) -> None:
        if len(records.items()) <= 3:
            return
        if not any("author" in r for ID, r in records.items()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with author field): {source.filename.name}"
            )

        if not any("title" in r for ID, r in records.items()):
            raise colrev_exceptions.ImportException(
                f"Import failed (no record with title field): {source.filename.name}"
            )

    if not source.filename.is_file():
        load_operation.review_manager.logger.debug(
            f"Did not find bib file {source.get_corresponding_bib_file().name} "
        )
        return {}

    with open(source.filename, encoding="utf8") as bibtex_file:
        contents = bibtex_file.read()
        bib_r = re.compile(r"@.*{.*,", re.M)
        if len(re.findall(bib_r, contents)) == 0:
            load_operation.review_manager.logger.error(
                f"Not a bib file? {source.filename.name}"
            )
            return {}

    __apply_file_fixes(load_operation=load_operation, filename=source.filename)

    with open(source.filename, encoding="utf8") as bibtex_file:
        records = load_operation.review_manager.dataset.load_records_dict(
            load_str=bibtex_file.read()
        )

    if len(records) == 0:
        load_operation.review_manager.report_logger.debug("No records loaded")
        load_operation.review_manager.logger.debug("No records loaded")
        return records

    drop_empty_fields(records=records)
    records = dict(sorted(records.items()))

    load_operation.review_manager.logger.debug(
        f"Loaded {source.get_corresponding_bib_file().name} "
        f"with {len(records)} records"
    )

    check_nr_in_bib(source=source, records=records)
    check_bib_file(source=source, records=records)
    return records
