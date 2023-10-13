#! /usr/bin/env python
"""Convenience functions to load ris files (based on rispy)"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import rispy
from rispy import BaseParser
from rispy.config import LIST_TYPE_TAGS
from rispy.config import TAG_KEY_MAPPING

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.load


# Based on https://github.com/aurimasv/translators/wiki/RIS-Tag-Map
REFERENCE_TYPES = {
    "JOUR": ENTRYTYPES.ARTICLE,
    "JFULL": ENTRYTYPES.ARTICLE,
    "ABST": ENTRYTYPES.ARTICLE,
    "INPR": ENTRYTYPES.ARTICLE,  # inpress
    "CONF": ENTRYTYPES.INPROCEEDINGS,
    "CPAPER": ENTRYTYPES.INPROCEEDINGS,
    "THES": ENTRYTYPES.PHDTHESIS,
    "REPT": ENTRYTYPES.TECHREPORT,
    "RPRT": ENTRYTYPES.TECHREPORT,
    "CHAP": ENTRYTYPES.INBOOK,
    "BOOK": ENTRYTYPES.BOOK,
    "NEWS": ENTRYTYPES.MISC,
    "BLOG": ENTRYTYPES.MISC,
}
KEY_MAP = {
    ENTRYTYPES.ARTICLE: {
        "ID": Fields.ID,
        "ENTRYTYPE": Fields.ENTRYTYPE,
        "year": Fields.YEAR,
        "authors": Fields.AUTHOR,
        "primary_title": Fields.TITLE,
        "secondary_title": Fields.JOURNAL,
        "notes_abstract": Fields.ABSTRACT,
        "volume": Fields.VOLUME,
        "number": Fields.NUMBER,
        "doi": Fields.DOI,
        "publisher": Fields.PUBLISHER,
        "url": Fields.URL,
        "fulltext": Fields.FULLTEXT,
        "pubmedid": Fields.PUBMED_ID,
        "keywords": Fields.KEYWORDS,
        "pages": Fields.PAGES,
    },
    ENTRYTYPES.INPROCEEDINGS: {
        "ID": Fields.ID,
        "ENTRYTYPE": Fields.ENTRYTYPE,
        "year": Fields.YEAR,
        "authors": Fields.AUTHOR,
        "primary_title": Fields.TITLE,
        "secondary_title": Fields.BOOKTITLE,
        "doi": Fields.DOI,
        "url": Fields.URL,
        "fulltext": Fields.FULLTEXT,
        "pubmedid": Fields.PUBMED_ID,
        "keywords": Fields.KEYWORDS,
        "pages": Fields.PAGES,
    },
    ENTRYTYPES.INBOOK: {
        "ID": Fields.ID,
        "ENTRYTYPE": Fields.ENTRYTYPE,
        "year": Fields.YEAR,
        "authors": Fields.AUTHOR,
        "primary_title": Fields.CHAPTER,
        "secondary_title": Fields.TITLE,
        "doi": Fields.DOI,
        "publisher": Fields.PUBLISHER,
        "edition": Fields.EDITION,
        "url": Fields.URL,
        "fulltext": Fields.FULLTEXT,
        "keywords": Fields.KEYWORDS,
        "pages": Fields.PAGES,
    },
    ENTRYTYPES.PHDTHESIS: {
        "ID": Fields.ID,
        "ENTRYTYPE": Fields.ENTRYTYPE,
        "year": Fields.YEAR,
        "authors": Fields.AUTHOR,
        "primary_title": Fields.TITLE,
        "url": Fields.URL,
    },
    ENTRYTYPES.TECHREPORT: {
        "ID": Fields.ID,
        "ENTRYTYPE": Fields.ENTRYTYPE,
        "year": Fields.YEAR,
        "authors": Fields.AUTHOR,
        "primary_title": Fields.TITLE,
        "url": Fields.URL,
        "fulltext": Fields.FULLTEXT,
        "keywords": Fields.KEYWORDS,
        "publisher": Fields.PUBLISHER,
        "pages": Fields.PAGES,
    },
    ENTRYTYPES.MISC: {
        "ID": Fields.ID,
        "ENTRYTYPE": Fields.ENTRYTYPE,
        "year": Fields.YEAR,
        "authors": Fields.AUTHOR,
        "primary_title": Fields.TITLE,
        "url": Fields.URL,
        "fulltext": Fields.FULLTEXT,
        "keywords": Fields.KEYWORDS,
        "publisher": Fields.PUBLISHER,
        "pages": Fields.PAGES,
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


class RISLoader:

    """Loads ris files

    RIS Format:

    TI  - Title of a paper

    RIS requires a mapping, which
    - can involve merging of RIS_FIELDS (e.g. AU / author fields)
    - can be conditional upon the ENTRYTYPE (e.g., publication_name: journal or booktitle)

    RIS_FIELD - BIB_FIELD

    """

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        ris_parser: BaseParser = DefaultRISParser,
        unique_id_field: str = "",
    ):
        self.load_operation = load_operation
        self.source = source
        self.ris_parser = ris_parser
        self.unique_id_field = unique_id_field

    def apply_ris_fixes(self, *, filename: Path) -> None:
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

    def __load_ris_entry(self, entry: dict) -> None:
        if "start_page" in entry and "end_page" in entry:
            entry[Fields.PAGES] = f"{entry.pop('start_page')}--{entry.pop('end_page')}"
        elif "start_page" in entry:
            entry[Fields.PAGES] = str(entry.pop("start_page"))

        for key in [
            self.ris_parser.DEFAULT_MAPPING[k]
            for k in self.ris_parser.DEFAULT_LIST_TAGS
        ]:
            if key not in entry:
                continue
            if key == Fields.URL:
                urls = entry[Fields.URL]
                for url in urls:
                    if url.endswith(".pdf"):
                        entry[Fields.FULLTEXT] = url
                    else:
                        entry[Fields.URL] = url
                        break
            elif key == Fields.KEYWORDS:
                entry[key] = ", ".join(entry[key])
            else:
                entry[key] = " and ".join(entry[key])

    def load_ris_entries(self) -> dict:
        """Load ris entries

        The resulting keys should coincide with those in the KEY_MAP
        but they can be adapted before calling the convert_to_records()"""

        # Note : depending on the source, a specific ris_parser implementation may be selected.
        # its DEFAULT_LIST_TAGS can be extended with list fiels that should be joined automatically

        if self.unique_id_field == "":
            self.load_operation.ensure_append_only(file=self.source.filename)

        with open(self.source.filename, encoding="utf-8") as ris_file:
            entries = rispy.load(file=ris_file, implementation=self.ris_parser)

        for entry in entries:
            self.__load_ris_entry(entry)

        return entries

    def convert_to_records(self, *, entries: dict) -> dict:
        """Converts ris entries it to bib records"""

        # Note : REFERENCE_TYPES and KEY_MAP are hard-coded (standard)
        # This function intentionally fails when the input does not comply
        # with this standard

        records: dict = {}
        for counter, entry in enumerate(entries):
            if self.unique_id_field == "":
                _id = str(counter + 1).zfill(5)
            else:
                _id = entry[self.unique_id_field].replace(" ", "").replace(";", "_")

            type_of_ref = entry["type_of_reference"]
            if type_of_ref not in REFERENCE_TYPES:
                raise NotImplementedError(f"Undefined reference type: {type_of_ref}")

            entry_type = REFERENCE_TYPES[type_of_ref]
            entry[Fields.ID] = _id
            entry[Fields.ENTRYTYPE] = entry_type

            if entry_type not in KEY_MAP:
                raise NotImplementedError(f"No KEY_MAP defined for {entry_type}")

            record: dict = {}
            for ris_key, key in KEY_MAP[entry_type].items():
                if ris_key in entry:
                    record[key] = entry[ris_key]

            records[_id] = record

        return records
