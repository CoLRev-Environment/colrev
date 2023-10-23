#! /usr/bin/env python
"""Convenience functions to load enl files


Usage::

    TODO

Example enl record::

    %T How Trust Leads to Commitment on Microsourcing Platforms
    %0 Journal Article
    %A Guo, Wenbo
    %A Straub, Detmar W.
    %A Zhang, Pengzhu
    %A Cai, Zhao
    %B Management Information Systems Quarterly
    %D 2021
    %8 September  1, 2021
    %V 45
    %N 3
    %P 1309-1348
    %U https://aisel.aisnet.org/misq/vol45/iss3/13
    %X IS research has extensively examined the role of trust in client-vendor relationships...

"""
from __future__ import annotations

import re
import typing
from typing import TYPE_CHECKING

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.load
    import colrev.settings.SearchSource


class NextLine(Exception):
    """NextLineException"""


class ParseError(Exception):
    """Parsing error"""


class ENLLoader:

    """Loads enl files"""

    PATTERN = r"^%[A-Z]{1,3} "

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        unique_id_field: str = "",
    ):
        self.load_operation = load_operation
        self.source = source
        self.unique_id_field = unique_id_field

        self.current: dict = {}
        self.pattern = re.compile(self.PATTERN)
        self.mapping = {
            "T": Fields.TITLE,
            "A": Fields.AUTHOR,
            "D": Fields.YEAR,
            "B": Fields.JOURNAL,
            "V": Fields.VOLUME,
            "N": Fields.NUMBER,
            "P": Fields.PAGES,
            "X": Fields.ABSTRACT,
            "U": Fields.URL,
            "8": "date",
            "0": "type",
        }
        self.list_tags = {"A": " and "}

    def is_tag(self, line: str) -> bool:
        """Determine if the line has a tag using regex."""
        return bool(self.pattern.match(line))

    def get_tag(self, line: str) -> str:
        """Get the tag from a line in the RIS file."""
        return line[1:3].rstrip()

    def get_content(self, line: str) -> str:
        """Get the content from a line"""
        return line[2:].strip()

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
        if tag not in self.mapping:
            print(f"load_utils_enl error: tag {tag} not in mapping")
            return
        name = self.mapping[tag]
        new_value = self.get_content(line)

        if tag in self.list_tags:
            self._add_list_value(name, new_value)
        else:
            self._add_single_value(name, new_value)

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

    def load_enl_entries(self) -> dict:
        """Loads enl entries"""

        if self.unique_id_field == "":
            self.load_operation.ensure_append_only(file=self.source.filename)

        # based on
        # https://github.com/MrTango/rispy/blob/main/rispy/parser.py
        # Note: skip-tags and unknown-tags can be handled
        # between load_enl_entries and convert_to_records.

        text = self.source.filename.read_text(encoding="utf-8")
        # clean_text?
        lines = text.split("\n")
        records_list = list(r for r in self.__parse_lines(lines) if r)

        records = {}
        for ind, record in enumerate(records_list):
            record[Fields.ID] = str(ind).rjust(6, "0")
            records[record[Fields.ID]] = record

        return records

    def convert_to_records(self, *, entries: dict) -> dict:
        """Converts enl entries it to bib records"""

        records: dict = {}
        for counter, entry in enumerate(entries.values()):
            if "type" in entry:
                if "Journal Article" == entry["type"]:
                    entry[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
                del entry["type"]
            else:
                entry[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

            for list_tag, delimiter in self.list_tags.items():
                list_field = self.mapping[list_tag]
                if list_field not in entry:
                    continue
                entry[list_field] = delimiter.join(entry[list_field])

            if self.unique_id_field == "":
                _id = str(counter + 1).zfill(5)
            else:
                _id = entry[self.unique_id_field].replace(" ", "").replace(";", "_")
            entry[Fields.ID] = _id
            records[_id] = entry

        return records
