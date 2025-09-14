#! /usr/bin/env python
"""Function to load nbib files"""
from __future__ import annotations

import logging
import re
import typing
from pathlib import Path

import colrev.loader.loader


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


class NextLine(Exception):
    """NextLineException"""


class ParseError(Exception):
    """Parsing error"""


class NBIBLoader(colrev.loader.loader.Loader):
    """Loads nbib files"""

    PATTERN = r"^[A-Z]{2,4}( ){1,2}- "

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        filename: Path,
        entrytype_setter: typing.Callable = lambda x: x,
        field_mapper: typing.Callable = lambda x: x,
        id_labeler: typing.Callable = lambda x: x,
        unique_id_field: str = "",
        logger: logging.Logger = logging.getLogger(__name__),
        format_names: bool = False,
    ):

        super().__init__(
            filename=filename,
            id_labeler=id_labeler,
            unique_id_field=unique_id_field,
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
            format_names=format_names,
        )

        self.current: dict = {}
        self.pattern = re.compile(self.PATTERN)

    @classmethod
    def get_nr_records(cls, filename: Path) -> int:
        """Get the number of records in the file"""
        count = 0
        with open(filename, encoding="utf-8") as file:
            for line in file:
                if line.startswith("TI "):
                    count += 1
        return count

    def _get_tag(self, line: str) -> str:
        """Get the tag from a line in the NBIB file."""
        return line[: line.find(" - ")].rstrip()

    def _get_content(self, line: str) -> str:
        """Get the content from a line"""
        return line[line.find(" - ") + 2 :].strip()

    def _add_tag(self, tag: str, line: str) -> None:
        new_value = self._get_content(line)

        if tag not in self.current:
            self.current[tag] = new_value
        elif isinstance(self.current[tag], str):
            self.current[tag] = [self.current[tag], new_value]
        elif isinstance(self.current[tag], list):
            self.current[tag].append(new_value)

    def _parse_tag(self, line: str) -> dict:
        tag = self._get_tag(line)

        if tag.strip() == "":
            return self.current

        self._add_tag(tag, line)
        raise NextLine

    def _parse_lines(self, lines: list) -> typing.Iterator[dict]:
        for line in lines:
            try:
                yield self._parse_tag(line)
                self.current = {}
            except NextLine:
                continue

    def load_records_list(self) -> list:
        """Loads nbib entries"""

        # based on
        # https://github.com/MrTango/rispy/blob/main/rispy/parser.py
        # Note: skip-tags and unknown-tags can be handled
        # between load_nbib_entries and convert_to_records.

        text = self.filename.read_text(encoding="utf-8")
        # clean_text?
        lines = text.split("\n")
        records_list = list(r for r in self._parse_lines(lines) if r)
        return records_list
