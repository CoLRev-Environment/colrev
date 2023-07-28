#! /usr/bin/env python
"""Convenience functions to load ris files (based on rispy)"""
from __future__ import annotations

import re
from pathlib import Path

import rispy
from rispy import BaseParser
from rispy.config import LIST_TYPE_TAGS
from rispy.config import TAG_KEY_MAPPING

# Based on https://github.com/aurimasv/translators/wiki/RIS-Tag-Map
REFERENCE_TYPES = {
    "JOUR": "article",
    "JFULL": "article",
    "ABST": "article",
    "INPR": "article",  # inpress
    "CONF": "inproceedings",
    "CPAPER": "inproceedings",
    "THES": "phdthesis",
    "REPT": "techreport",
    "RPRT": "techreport",
    "CHAP": "inbook",
    "BOOK": "book",
}
KEY_MAP = {
    "article": {
        "ID": "ID",
        "ENTRYTYPE": "ENTRYTYPE",
        "year": "year",
        "authors": "author",
        "primary_title": "title",
        "secondary_title": "journal",
        "notes_abstract": "abstract",
        "volume": "volume",
        "number": "number",
        "doi": "doi",
        "publisher": "publisher",
        "url": "url",
        "fulltext": "fulltext",
        "pubmedid": "pubmedid",
        "keywords": "keywords",
        "pages": "pages",
    },
    "inproceedings": {
        "ID": "ID",
        "ENTRYTYPE": "ENTRYTYPE",
        "year": "year",
        "authors": "author",
        "primary_title": "title",
        "secondary_title": "booktitle",
        "doi": "doi",
        "url": "url",
        "fulltext": "fulltext",
        "pubmedid": "pubmedid",
        "keywords": "keywords",
        "pages": "pages",
    },
    "inbook": {
        "ID": "ID",
        "ENTRYTYPE": "ENTRYTYPE",
        "year": "year",
        "authors": "author",
        "primary_title": "chapter",
        "secondary_title": "title",
        "doi": "doi",
        "publisher": "publisher",
        "edition": "edition",
        "url": "url",
        "fulltext": "fulltext",
        "keywords": "keywords",
        "pages": "pages",
    },
    "techreport": {
        "ID": "ID",
        "ENTRYTYPE": "ENTRYTYPE",
        "year": "year",
        "authors": "author",
        "primary_title": "title",
        "url": "url",
        "fulltext": "fulltext",
        "keywords": "keywords",
        "publisher": "publisher",
        "pages": "pages",
    },
}


class DefaultRISParser(BaseParser):
    """Default parser for RIS files."""

    START_TAG = "TY"
    IGNORE = ["FN", "VR", "EF"]
    PATTERN = r"^[A-Z][A-Z0-9]+ |^ER\s?|^EF\s?"
    DEFAULT_MAPPING = TAG_KEY_MAPPING
    DEFAULT_LIST_TAGS = LIST_TYPE_TAGS + ["UR"]

    def get_content(self, line: str) -> str:
        "Get the content from a line."
        return line[line.find(" - ") + 2 :].strip()

    def is_header(self, line: str) -> bool:
        "Check whether the line is a header element"
        return not re.match("[A-Z0-9]+  - ", line)


def apply_ris_fixes(*, filename: Path) -> None:
    """Fix common defects in RIS files"""

    # Error to fix: for lists of keywords, each line should start with the KW tag

    with open(filename, encoding="UTF-8") as file:
        lines = [line.rstrip("\n") for line in file]
        for i, line in enumerate(lines):
            if line.startswith("PMID "):
                lines[i] = line.replace("PMID ", "PM ")

        # add missing start tags in lists (like KW)
        processing_tag = ""
        for i, line in enumerate(lines):
            tag_match = re.match(r"^[A-Z][A-Z0-9]+(\s+)-", line)  # |^ER\s?|^EF\s?
            if tag_match:
                processing_tag = tag_match.group()
            elif line == "":
                processing_tag = ""
                continue
            elif processing_tag == "":
                continue
            else:
                lines[i] = f"{processing_tag} {line}"

    with open(filename, "w", encoding="utf-8") as file:
        for line in lines:
            file.write(f"{line}\n")


def load_ris_entries(
    *, filename: Path, ris_parser: BaseParser = DefaultRISParser
) -> dict:
    """Load ris entries

    The resulting keys should coincide with those in the KEY_MAP
    but they can be adapted before calling the convert_to_records()"""

    # Note : depending on the source, a specific ris_parser implementation may be selected.
    # its DEFAULT_LIST_TAGS can be extended with list fiels that should be joined automatically

    with open(filename, encoding="utf-8") as ris_file:
        entries = rispy.load(file=ris_file, implementation=ris_parser)

    for entry in entries:
        if "pages" in entry:
            continue
        if "start_page" in entry and "end_page" in entry:
            entry["pages"] = f"{entry.pop('start_page')}--{entry.pop('end_page')}"
        elif "start_page" in entry:
            entry["pages"] = f"{entry.pop('start_page')}"

        for key in [
            ris_parser.DEFAULT_MAPPING[k] for k in ris_parser.DEFAULT_LIST_TAGS
        ]:
            if key not in entry:
                continue
            if "author" in key:
                entry[key] = " and ".join(entry[key])
            elif "url" == key:
                urls = entry["url"]
                for url in urls:
                    if url.endswith(".pdf"):
                        entry["fulltext"] = url
                    else:
                        entry["url"] = url
                        break
            else:
                entry[key] = ", ".join(entry[key])

    return entries


def convert_to_records(entries: dict) -> dict:
    """Converts ris entries it to bib records"""

    # Note : REFERENCE_TYPES and KEY_MAP are hard-coded (standard)
    # This function intentionally fails when the input does not comply
    # with this standard

    records: dict = {}
    for counter, entry in enumerate(entries):
        _id = str(counter + 1).zfill(5)

        type_of_ref = entry["type_of_reference"]
        if type_of_ref not in REFERENCE_TYPES:
            raise NotImplementedError(f"Undefined reference type: {type_of_ref}")

        entry_type = REFERENCE_TYPES[type_of_ref]
        entry["ID"] = _id
        entry["ENTRYTYPE"] = entry_type

        if entry_type not in KEY_MAP:
            raise NotImplementedError(f"No KEY_MAP defined for {entry_type}")

        record: dict = {}
        for ris_key, key in KEY_MAP[entry_type].items():
            if ris_key in entry:
                record[key] = entry[ris_key]

        records[_id] = record

    return records
