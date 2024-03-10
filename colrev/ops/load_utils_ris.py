#! /usr/bin/env python
"""Convenience functions to load RIS files

RIS requires a mapping from the RIS_FIELDS to the standard CoLRev Fields (see CEP 002), which

- can involve merging of RIS_FIELDS (e.g. AU / author fields)
- can be conditional upon the ENTRYTYPE (e.g., publication_name: journal or booktitle)

Example RIS record::

    TY  - JOUR
    AU  - Guo, Wenbo
    AU  - Straub, Detmar W.
    AU  - Zhang, Pengzhu
    AU  - Cai, Zhao
    DA  - 2021/09/01
    DO  - 10.25300/MISQ/2021/16100
    ID  - Guo2021
    T2  - Management Information Systems Quarterly
    TI  - How Trust Leads to Commitment on Microsourcing Platforms
    VL  - 45
    IS  - 3
    SP  - 1309
    EP  - 1348
    UR  - https://aisel.aisnet.org/misq/vol45/iss3/13
    PB  - Association for Information Systems
    ER  -

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


class RISLoader(colrev.ops.loader.Loader):
    """Loads ris files"""

    PATTERN = r"^[A-Z0-9]{2,4} "

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

    def apply_ris_fixes(self) -> None:
        """Fix common defects in RIS files"""

        # Error to fix: for lists of keywords, each line should start with the KW tag

        with open(self.filename, encoding="UTF-8") as file:
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

        with open(self.filename, "w", encoding="utf-8") as file:
            for line in lines:
                file.write(f"{line}\n")

    def _get_tag(self, line: str) -> str:
        """Get the tag from a line in the RIS file."""
        return line[0 : line.find(" ")].rstrip()

    def _get_content(self, line: str) -> str:
        """Get the content from a line"""
        return line[line.find(" - ") + 3 :].strip()

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

    def _clean_text(self, text: str) -> str:
        # Example:
        # Provider: JSTOR http://www.jstor.org
        # Database: JSTOR
        # Content: text/plain; charset="UTF-8"

        lines = []
        for line in text.split("\n"):
            if re.match(self.pattern, line):
                lines.append(line)
            if line.strip() in ["", "\n"]:
                lines.append(line)
        lines.append("")
        return "\n".join(lines)

    def load_records_list(
        self, *, content: str = "", combine_sp_ep: bool = True
    ) -> list:
        """Load ris entries

        The resulting keys should coincide with those in the KEY_MAP
        but they can be adapted before calling the convert_to_records()"""

        # Note : depending on the source, a specific ris_parser implementation may be selected.
        # its DEFAULT_LIST_TAGS can be extended with list fields that should be joined automatically

        if content == "":
            content = self.filename.read_text(encoding="utf-8")
            content = self._clean_text(content)

        lines = content.split("\n")
        records_list = list(r for r in self._parse_lines(lines) if r)

        return records_list
