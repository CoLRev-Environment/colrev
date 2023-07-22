#! /usr/bin/env python
"""Convenience functions to load bib files"""
from __future__ import annotations

import itertools
import os
import re
import string
import typing
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.ops.load

# if typing:


def __apply_file_fixes(*, load_operation: colrev.ops.load.Load, filename: Path) -> None:
    # pylint: disable=duplicate-code

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


def __resolve_non_unique_ids(
    *, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
) -> None:
    def get_unique_id(*, non_unique_id: str, id_list: list[str]) -> str:
        order = 0
        letters = list(string.ascii_lowercase)
        temp_id = non_unique_id
        next_unique_id = temp_id
        appends: list = []
        while next_unique_id in id_list:
            if len(appends) == 0:
                order += 1
                appends = list(itertools.product(letters, repeat=order))
            next_unique_id = temp_id + "".join(list(appends.pop(0)))

        return next_unique_id

    def inplace_change_second(
        *, filename: Path, old_string: str, new_string: str
    ) -> None:
        new_file_lines = []
        with open(filename, encoding="utf8") as file:
            first_read = False
            replaced = False
            for line in file.readlines():
                if old_string in line and not first_read:
                    first_read = True
                if old_string in line and first_read and not replaced:
                    line = line.replace(old_string, new_string)
                    replaced = True
                new_file_lines.append(line)

            # s = f.read()
            # if old_string not in s:
            #     return
        with open(filename, "w", encoding="utf8") as file:
            for new_file_line in new_file_lines:
                file.write(new_file_line)

    if not source.get_corresponding_bib_file().is_file():
        return

    with open(source.get_corresponding_bib_file(), encoding="utf8") as bibtex_file:
        cr_dict = load_operation.review_manager.dataset.load_records_dict(
            load_str=bibtex_file.read()
        )

    ids_to_update = []
    current_ids = list(cr_dict.keys())
    for record in cr_dict.values():
        if len([x for x in current_ids if x == record["ID"]]) > 1:
            new_id = get_unique_id(non_unique_id=record["ID"], id_list=current_ids)
            ids_to_update.append([record["ID"], new_id])
            current_ids.append(new_id)

    if len(ids_to_update) > 0:
        load_operation.review_manager.dataset.add_changes(
            path=source.get_corresponding_bib_file()
        )
        load_operation.review_manager.create_commit(
            msg=f"Save original search file: {source.get_corresponding_bib_file().name}",
        )

        for old_id, new_id in ids_to_update:
            load_operation.review_manager.logger.info(
                f"Resolve ID to ensure unique colrev_origins: {old_id} -> {new_id}"
            )
            load_operation.review_manager.report_logger.info(
                f"Resolve ID to ensure unique colrev_origins: {old_id} -> {new_id}"
            )
            inplace_change_second(
                filename=source.get_corresponding_bib_file(),
                old_string=f"{old_id},",
                new_string=f"{new_id},",
            )
        load_operation.review_manager.dataset.add_changes(
            path=source.get_corresponding_bib_file()
        )
        load_operation.review_manager.create_commit(
            msg=f"Resolve non-unique IDs in {source.get_corresponding_bib_file().name}"
        )


def load_bib_file(
    load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
) -> dict:
    """Load a bib file and return records dict"""

    def fix_keys(*, records: dict) -> dict:
        for record in records.values():
            record = {
                re.sub("[0-9a-zA-Z_]+", "1", k.replace(" ", "_")): v
                for k, v in record.items()
            }
        return records

    def set_incremental_ids(*, records: dict) -> None:
        # if IDs to set for some records
        if 0 != len([r for r in records if "ID" not in r]):
            i = 1
            for record in records.values():
                if "ID" not in record:
                    record["ID"] = f"{i+1}".rjust(10, "0")
                    i += 1

    def drop_empty_fields(*, records: dict) -> None:
        for record_id in records:
            records[record_id] = {
                k: v for k, v in records[record_id].items() if v is not None
            }
            records[record_id] = {
                k: v for k, v in records[record_id].items() if v != "nan"
            }

    def drop_fields(*, records: dict) -> None:
        for record_id in records:
            records[record_id] = {
                k: v
                for k, v in records[record_id].items()
                if k not in ["colrev_status", "colrev_masterdata_provenance"]
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

    def __check_bib_file(
        *, source: colrev.settings.SearchSource, records: dict
    ) -> None:
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

    __apply_file_fixes(load_operation=load_operation, filename=source.filename)
    __resolve_non_unique_ids(load_operation=load_operation, source=source)

    with open(source.filename, encoding="utf8") as bibtex_file:
        contents = bibtex_file.read()
        bib_r = re.compile(r"@.*{.*,", re.M)
        if len(re.findall(bib_r, contents)) == 0:
            load_operation.review_manager.logger.error(
                f"Not a bib file? {source.filename.name}"
            )

    with open(source.filename, encoding="utf8") as bibtex_file:
        records = load_operation.review_manager.dataset.load_records_dict(
            load_str=bibtex_file.read()
        )

    if len(records) == 0:
        load_operation.review_manager.report_logger.debug("No records loaded")
        load_operation.review_manager.logger.debug("No records loaded")
        return records

    fix_keys(records=records)
    set_incremental_ids(records=records)
    drop_empty_fields(records=records)
    drop_fields(records=records)
    records = dict(sorted(records.items()))

    load_operation.review_manager.logger.debug(
        f"Loaded {source.get_corresponding_bib_file().name} "
        f"with {len(records)} records"
    )

    check_nr_in_bib(source=source, records=records)
    __check_bib_file(source=source, records=records)
    return records
