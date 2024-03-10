#! /usr/bin/env python
"""Convenience functions to load ENL files

ENL requires a mapping from the ENL_FIELDS to the standard CoLRev Fields (see CEP 002), which

- can involve merging of ENL_FIELDS (e.g. AU / author fields)
- can be conditional upon the ENTRYTYPE (e.g., publication_name: journal or booktitle)

Example ENL record::

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

import logging
import re
import typing
from pathlib import Path
from typing import Callable

import colrev.ops.loader


class NextLine(Exception):
    """NextLineException"""


class ParseError(Exception):
    """Parsing error"""


class ENLLoader(colrev.ops.loader.Loader):
    """Loads enl files"""

    PATTERN = r"^%[A-Z]{1,3} "

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        filename: Path,
        entrytype_setter: Callable,
        field_mapper: Callable,
        id_labeler: typing.Optional[Callable] = None,
        unique_id_field: str = "",
        logger: typing.Optional[logging.Logger] = None,
    ):
        self.filename = filename

        self.unique_id_field = unique_id_field
        assert id_labeler is not None or unique_id_field != ""
        self.id_labeler = id_labeler
        self.entrytype_setter = entrytype_setter
        self.field_mapper = field_mapper

        self.current: dict = {}
        self.pattern = re.compile(self.PATTERN)

        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger
        super().__init__(
            filename=filename,
            id_labeler=id_labeler,
            unique_id_field=unique_id_field,
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
        )

    def get_tag(self, line: str) -> str:
        """Get the tag from a line in the ENL file."""
        return line[1:3].rstrip()

    def get_content(self, line: str) -> str:
        """Get the content from a line"""
        return line[2:].strip()

    def _add_tag(self, tag: str, line: str) -> None:
        new_value = self.get_content(line)

        if tag not in self.current:
            self.current[tag] = new_value
        elif isinstance(self.current[tag], str):
            self.current[tag] = [self.current[tag], new_value]
        elif isinstance(self.current[tag], list):
            self.current[tag].append(new_value)

    def _parse_tag(self, line: str) -> dict:
        tag = self.get_tag(line)

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
        """Loads enl entries"""

        # based on
        # https://github.com/MrTango/rispy/blob/main/rispy/parser.py
        # Note: skip-tags and unknown-tags can be handled
        # between load_enl_entries and convert_to_records.

        text = self.filename.read_text(encoding="utf-8")
        # clean_text?
        lines = text.split("\n")
        records_list = list(r for r in self._parse_lines(lines) if r)
        return records_list
