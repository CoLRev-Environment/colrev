#! /usr/bin/env python
"""Convenience functions to load nbib files

NBIB requires a mapping from the NBIB_FIELDS to the standard CoLRev Fields (see CEP 002), which

- can involve merging of NBIB_FIELDS (e.g. AU / author fields)
- can be conditional upon the ENTRYTYPE (e.g., publication_name: journal or booktitle)

Usage::

    import colrev.ops.load_utils_nbib
    from colrev.constants import Fields, ENTRYTYPES

    # The mappings need to be adapted to the SearchSource
    entrytype_map = {
        "Journal Article": ENTRYTYPES.ARTICLE,
        "Conference Proceedings": ENTRYTYPES.INPROCEEDINGS,
    }
    key_map = {
        ENTRYTYPES.ARTICLE: {
            "DP": Fields.YEAR,
            "AU": Fields.AUTHOR,
            "TI": Fields.TITLE,
            "JT": Fields.JOURNAL,
            "VI": Fields.VOLUME,
            "IP": Fields.NUMBER,
            "PG": Fields.PAGES,
            "U": Fields.URL,
        },
        ENTRYTYPES.INPROCEEDINGS: {
            "DP": Fields.YEAR,
            "AU": Fields.AUTHOR,
            "TI": Fields.TITLE,
            "JT": Fields.BOOKTITLE,
            "U": Fields.URL,
            "PG": Fields.PAGES,
        },
    }

    nbib_loader = colrev.ops.load_utils_nbib.NBIBLoader(
        load_operation=load_operation,
        source=self.search_source,
        list_fields={"A": " and "},
    )

    # Note : fixes can be applied before each of the following steps

    records = nbib_loader.load_nbib_entries()

    for record_dict in records.values():
        nbib_loader.apply_entrytype_mapping(record_dict=record_dict, entrytype_map=entrytype_map)
        nbib_loader.map_keys(record_dict=record_dict, key_map=key_map)

Example nbib record::

    OWN - ERIC
    TI  - How Trust Leads to Commitment on Microsourcing Platforms
    AU  - Guo, Wenbo
    AU  - Straub, Detmar W.
    AU  - Zhang, Pengzhu
    AU  - Cai, Zhao
    JT  - MIS Quarterly
    DP  - 2021
    VI  - 45
    IP  - 3
    PG  - 1309-1348
"""
from __future__ import annotations

import re
import typing
from typing import TYPE_CHECKING

from colrev.constants import Colors
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.load

# pylint: disable=too-few-public-methods


class NextLine(Exception):
    """NextLineException"""


class ParseError(Exception):
    """Parsing error"""


class NBIBLoader:
    """Loads nbib files"""

    PATTERN = r"^[A-Z]{2,4}( ){1,2}- "

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

        self.current: dict = {}
        self.pattern = re.compile(self.PATTERN)
        self.list_fields = list_fields

    def is_tag(self, line: str) -> bool:
        """Determine if the line has a tag using regex."""
        return bool(self.pattern.match(line))

    def get_tag(self, line: str) -> str:
        """Get the tag from a line in the NBIB file."""
        return line[: line.find(" - ")].rstrip()

    def get_content(self, line: str) -> str:
        """Get the content from a line"""
        return line[line.find(" - ") + 2 :].strip()

    def _add_single_value(self, name: str, value: str) -> None:
        """Process a single line."""
        self.current[name] = value

    def _add_list_value(self, name: str, value: str) -> None:
        """Process tags with multiple values."""
        try:
            self.current[name].append(value)
        except KeyError:
            self.current[name] = [value]

    def _add_tag(self, tag: str, line: str) -> None:
        name = tag
        new_value = self.get_content(line)

        if tag in self.list_fields:
            self._add_list_value(name, new_value)
        else:
            self._add_single_value(tag, new_value)

    def _parse_tag(self, line: str) -> dict:
        tag = self.get_tag(line)

        if tag.strip() == "":
            return self.current

        self._add_tag(tag, line)
        raise NextLine

    def __parse_lines(self, lines: list) -> typing.Iterator[dict]:
        for line in lines:
            try:
                yield self._parse_tag(line)
                self.current = {}
            except NextLine:
                continue

    def load_nbib_entries(self) -> dict:
        """Loads nbib entries"""

        if self.unique_id_field == "":
            self.load_operation.ensure_append_only(file=self.source.filename)

        # based on
        # https://github.com/MrTango/rispy/blob/main/rispy/parser.py
        # Note: skip-tags and unknown-tags can be handled
        # between load_nbib_entries and convert_to_records.

        text = self.source.filename.read_text(encoding="utf-8")
        # clean_text?
        lines = text.split("\n")
        records_list = list(r for r in self.__parse_lines(lines) if r)

        records = {}
        for ind, record in enumerate(records_list):
            record[Fields.ID] = str(ind + 1).rjust(6, "0")
            for list_field, connective in self.list_fields.items():
                if list_field in record:
                    record[list_field] = connective.join(record[list_field])
            records[record[Fields.ID]] = record
        return records

    def apply_entrytype_mapping(
        self, *, record_dict: dict, entrytype_map: dict
    ) -> None:
        """Apply the mapping of nbib PT fields to CoLRev ENTRYTYPES"""

        if record_dict["PT"] not in entrytype_map:
            msg = f"{Colors.RED}PT={record_dict['PT']} not yet supported{Colors.END}"
            if not self.load_operation.review_manager.force_mode:
                raise NotImplementedError(msg)
            self.load_operation.review_manager.logger.error(msg)
            return

        entrytype = entrytype_map[record_dict["PT"]]
        record_dict[Fields.ENTRYTYPE] = entrytype

    def map_keys(self, *, record_dict: dict, key_map: dict) -> None:
        """Converts nbib entries it to bib records"""
        entrytype = record_dict[Fields.ENTRYTYPE]

        # NBIB-keys > standard keys
        for ris_key in list(record_dict.keys()):
            if ris_key in [Fields.ENTRYTYPE, Fields.ID]:
                continue
            if ris_key not in key_map[entrytype]:
                del record_dict[ris_key]
                # print/notify: ris_key
                continue
            standard_key = key_map[entrytype][ris_key]
            record_dict[standard_key] = record_dict.pop(ris_key)

        # Set unique_id (if any)
        if self.unique_id_field != "":
            _id = record_dict[self.unique_id_field].replace(" ", "").replace(";", "_")
            record_dict[Fields.ID] = _id
