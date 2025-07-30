#! /usr/bin/env python
"""Function to load bib files"""
from __future__ import annotations

import itertools
import logging
import os
import re
import string
import typing
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

import colrev.exceptions as colrev_exceptions
import colrev.loader.loader
from colrev.constants import Fields
from colrev.constants import FieldSet
from colrev.constants import RecordState

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments


def run_fix_bib_file(filename: Path, *, logger: logging.Logger) -> None:
    """Fix a BibTeX file"""
    # pylint: disable=too-many-statements

    def fix_key(
        file: typing.IO, line: bytes, replacement_line: bytes, seekpos: int
    ) -> int:
        logger.info(
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

    def generate_next_unique_id(
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

    if filename is not None:

        with open(filename, encoding="utf8") as bibtex_file:
            contents = bibtex_file.read()
            if len(contents) < 10:
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

                    if any(x in current_id_str for x in [";"]):
                        replacement_line = re.sub(
                            r";",
                            r"_",
                            line.decode("utf-8"),
                        ).encode("utf-8")
                        seekpos = fix_key(file, line, replacement_line, seekpos)

                    if current_id_str in record_ids:
                        next_id = generate_next_unique_id(
                            temp_id=current_id_str, existing_ids=record_ids
                        )
                        logger.info(f"Fix duplicate ID: {current_id_str} >> {next_id}")

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


def check_valid_bib(filename: Path, logger: logging.Logger) -> None:
    """Check if the file is a valid bib file."""

    with open(filename, encoding="utf8") as file:
        contents = "".join(line for _, line in zip(range(20), file))

        bib_r = re.compile(r"@.*{.*,", re.M)
        if len(contents.strip()) > 0:
            if len(re.findall(bib_r, contents)) == 0:
                logger.error(f"Not a bib file? {filename.name}")
                raise colrev_exceptions.UnsupportedImportFormatError(filename)


def parse_provenance(value: str) -> dict:
    """Parses the provenance field."""
    parsed_dict = {}
    items = [x.strip() for x in value.split("; ") if x.strip()]
    for item in items:
        if ":" in item:
            key, source = item.split(":", 1)
            source_parts = source.split(";")
            parsed_dict[key.strip()] = {
                "source": source_parts[0].strip(),
                "note": (source_parts[1].strip() if len(source_parts) > 1 else ""),
            }
    return parsed_dict


def extract_content(text: str) -> str:
    """Extracts the content of a field."""
    match = re.match(r"^\s*\{(.*)\},?\s*$", text)
    return match.group(1).strip() if match else text


def handle_new_entry(
    records: List[Dict[str, Any]], current_record: Dict[str, Any], line: str
) -> Dict[str, Any]:
    """Handles a new record entry."""
    if current_record:
        records.append(current_record)

    match = re.match(r"@([a-zA-Z]+)\s*\{([^,]+),", line)
    if match:
        entry_type, entry_id = match.groups()
        return {
            Fields.ID: entry_id.strip(),
            Fields.ENTRYTYPE: entry_type.strip(),
        }

    return {}


def process_key_value(
    current_record: Dict[str, Any], current_key: str, current_value: str, line: str
) -> tuple[str, str]:
    """Processes a key-value pair inside an entry."""
    if re.match(r"^\s*[a-zA-Z0-9._-]+\s*=", line):
        if current_key:
            store_current_key_value(current_record, current_key, current_value)
        key, value = map(str.strip, line.split("=", 1))
        return key, value
    return current_key, current_value + " " + line.strip()


def store_current_key_value(
    current_record: Dict[str, Any], current_key: str, current_value: str
) -> None:
    """Stores the processed key-value pair into the current entry."""
    if not current_key or not current_record:
        return

    if current_key in [Fields.MD_PROV, Fields.D_PROV]:
        current_record[current_key] = parse_provenance(current_value.strip(", {}"))
    elif current_key == Fields.STATUS:
        current_record[current_key] = RecordState[current_value.strip(", {}")]
    elif current_key == Fields.DOI:
        current_record[current_key] = current_value.strip(", {} ").upper()
    elif current_key in [Fields.ORIGIN] + list(FieldSet.LIST_FIELDS):
        current_record[current_key] = [
            el.strip(";")
            for el in current_value.strip(", {} ").split("; ")
            if el.strip()
        ]
    else:
        current_record[current_key] = extract_content(current_value)


def process_lines(
    file: typing.TextIO, header_only: bool = False
) -> List[Dict[str, Any]]:
    """Processes each line of the file and constructs records.

    Args:
        file (TextIO): The file object to read from.
        header_only (bool): If True, only extract required header fields.

    Returns:
        List[Dict[str, Any]]: Parsed records.
    """

    records: List[Dict[str, Any]] = []
    current_record: Dict[str, Any] = {}
    current_key = ""
    current_value = ""
    inside_record = False
    skip_remaining_non_header_fields = False

    header_fields = {
        Fields.ID,
        Fields.ORIGIN,
        Fields.STATUS,
        Fields.FILE,
        Fields.SCREENING_CRITERIA,
        Fields.MD_PROV,
    }

    for line in file:
        line = line.strip()
        if skip_remaining_non_header_fields and not line.startswith("@"):
            continue
        if not line or line.startswith("%"):
            continue

        if line.startswith("@"):
            if header_only and current_record:
                records.append(current_record)
            current_record = handle_new_entry(records, current_record, line)
            inside_record = True
            current_key = ""
            current_value = ""
            skip_remaining_non_header_fields = False
            continue

        if inside_record:
            current_key, current_value = process_key_value(
                current_record, current_key, current_value, line
            )

            # If header_only is enabled, stop processing after collecting required headers
            if header_only and current_key in header_fields:
                store_current_key_value(current_record, current_key, current_value)
                # Given that the header fields are ordered, we can stop parsing further fields
                if current_key == Fields.MD_PROV:
                    skip_remaining_non_header_fields = True

        if line.strip() == "}":
            current_value = current_value.rstrip("}")
            store_current_key_value(current_record, current_key, current_value)

    if current_record:
        store_current_key_value(current_record, current_key, current_value)
        records.append(current_record)

    return records


def run_resolve_crossref(records: dict, *, logger: logging.Logger) -> None:
    """Resolve cross-references between records"""
    # Handle cross-references between records
    crossref_ids = []
    for record_dict in records.values():
        if "crossref" not in record_dict:
            continue

        crossref_record = records.get(record_dict["crossref"], None)

        if not crossref_record:
            logger.error(f"crossref record (ID={record_dict['crossref']}) not found")
            continue
        crossref_ids.append(crossref_record["ID"])
        for key, value in crossref_record.items():
            if key not in record_dict:
                record_dict[key] = value
        del record_dict["crossref"]

    for crossref_id in crossref_ids:
        del records[crossref_id]


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
        format_names: bool = False,
        resolve_crossref: bool = False,
    ):
        self.resolve_crossref = resolve_crossref

        super().__init__(
            filename=filename,
            id_labeler=id_labeler,
            unique_id_field=unique_id_field,
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
            format_names=format_names,
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

    def get_record_header_items(self) -> dict:
        """Get the record header items efficiently using load_records_list()."""
        record_header_list = self.load_records_list(header_only=True)
        return {r[Fields.ID]: r for r in record_header_list}

    def load_records_list(self, header_only: bool = False) -> List[Dict[str, Any]]:
        """Parses the file and returns either full records or just header fields."""
        records = []
        check_valid_bib(self.filename, self.logger)

        with open(self.filename, encoding="utf-8") as file:
            records = process_lines(file, header_only=header_only)

        records.sort(key=lambda x: x[Fields.ID])
        return records
