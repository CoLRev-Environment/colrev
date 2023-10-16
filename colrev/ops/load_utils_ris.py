#! /usr/bin/env python
"""Convenience functions to load ris files (based on rispy)"""
from __future__ import annotations

import re
import typing
from pathlib import Path
from typing import TYPE_CHECKING

from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.load


class NextLine(Exception):
    """NextLineException"""


class ParseError(Exception):
    """Parsing error"""


class RISLoader:

    """Loads ris files

    RIS Format:

    TI  - Title of a paper

    RIS requires a mapping, which
    - can involve merging of RIS_FIELDS (e.g. AU / author fields)
    - can be conditional upon the ENTRYTYPE (e.g., publication_name: journal or booktitle)

    RIS_FIELD - BIB_FIELD

    """

    PATTERN = r"^[A-Z0-9]{2,4} "

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
        self.list_fields = list_fields
        self.current: dict = {}
        self.pattern = re.compile(self.PATTERN)

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

    def is_tag(self, line: str) -> bool:
        """Determine if the line has a tag using regex."""
        return bool(self.pattern.match(line))

    def get_tag(self, line: str) -> str:
        """Get the tag from a line in the RIS file."""
        return line[0 : line.find(" ")].rstrip()

    def get_content(self, line: str) -> str:
        """Get the content from a line"""
        return line[line.find(" - ") + 3 :].strip()

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
        new_value = self.get_content(line)

        if tag in self.list_fields:
            self._add_list_value(tag, new_value)
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

    def __clean_text(self, text: str) -> str:
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

    def load_ris_records(self, *, combine_sp_ep: bool = True) -> dict:
        """Load ris entries

        The resulting keys should coincide with those in the KEY_MAP
        but they can be adapted before calling the convert_to_records()"""

        # Note : depending on the source, a specific ris_parser implementation may be selected.
        # its DEFAULT_LIST_TAGS can be extended with list fiels that should be joined automatically

        if self.unique_id_field == "":
            self.load_operation.ensure_append_only(file=self.source.filename)

        text = self.source.filename.read_text(encoding="utf-8")
        text = self.__clean_text(text)
        lines = text.split("\n")
        records_list = list(r for r in self.__parse_lines(lines) if r)
        for counter, entry in enumerate(records_list):
            _id = str(counter + 1).zfill(5)

            entry[Fields.ID] = _id
            for list_field, connective in self.list_fields.items():
                if list_field in entry:
                    entry[list_field] = connective.join(entry[list_field])
            if combine_sp_ep:
                if "SP" in entry and "EP" in entry:
                    entry["SP"] = f"{entry.pop('SP')}--{entry.pop('EP')}"

        return {r["ID"]: r for r in records_list}
