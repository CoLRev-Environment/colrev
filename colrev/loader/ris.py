#! /usr/bin/env python
"""Function to load RIS files."""

from __future__ import annotations

import logging
import re
import typing
from pathlib import Path

import colrev.loader.loader
from colrev.constants import ENTRYTYPES, Fields

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


class NextLine(Exception):
    """NextLineException."""


class ParseError(Exception):
    """Parsing error."""


RIS_ENTRYTYPES = {
    "JOUR": ENTRYTYPES.ARTICLE,
    "JFULL": ENTRYTYPES.ARTICLE,
    "ABST": ENTRYTYPES.ARTICLE,
    "INPR": ENTRYTYPES.ARTICLE,
    "CONF": ENTRYTYPES.INPROCEEDINGS,
    "CPAPER": ENTRYTYPES.INPROCEEDINGS,
    "CHAP": ENTRYTYPES.INBOOK,
    "BOOK": ENTRYTYPES.BOOK,
    "THES": ENTRYTYPES.PHDTHESIS,
    "REPT": ENTRYTYPES.TECHREPORT,
    "RPRT": ENTRYTYPES.TECHREPORT,
    "NEWS": ENTRYTYPES.MISC,
    "BLOG": ENTRYTYPES.MISC,
}


def set_entrytype(record_dict: dict) -> None:
    """Apply CoLRev's generic interpretation of the RIS reference type."""
    raw_type = record_dict.pop("TY", "")
    ris_type = str(raw_type).strip().upper()
    record_dict[Fields.ENTRYTYPE] = RIS_ENTRYTYPES.get(ris_type, ENTRYTYPES.MISC)


def _first_non_empty(record_dict: dict, tags: tuple[str, ...]) -> object | None:
    """Return the first populated value in *tags*."""
    for tag in tags:
        value = record_dict.get(tag)
        if isinstance(value, list):
            if any(str(item).strip() for item in value):
                return value
        elif value is not None and str(value).strip():
            return value
    return None


def _map_first(record_dict: dict, target: str, tags: tuple[str, ...]) -> None:
    """Map the first populated RIS tag without replacing existing metadata."""
    value = _first_non_empty(record_dict, tags)
    if target not in record_dict and value is not None:
        record_dict[target] = value
    if target in record_dict and str(record_dict[target]).strip():
        for tag in tags:
            record_dict.pop(tag, None)


def map_fields(record_dict: dict) -> None:
    """Map common RIS tags to conservative, format-independent CoLRev fields."""
    _map_first(record_dict, Fields.TITLE, ("TI", "T1"))
    _map_first(record_dict, Fields.YEAR, ("PY", "Y1", "DA"))
    _map_first(record_dict, Fields.AUTHOR, ("AU", "A1"))

    if record_dict.get(Fields.ENTRYTYPE) == ENTRYTYPES.ARTICLE:
        _map_first(record_dict, Fields.JOURNAL, ("JO", "JF", "JA", "T2"))
    elif record_dict.get(Fields.ENTRYTYPE) == ENTRYTYPES.INPROCEEDINGS:
        _map_first(record_dict, Fields.BOOKTITLE, ("T2",))

    for tag, target in (
        ("DO", Fields.DOI),
        ("VL", Fields.VOLUME),
        ("IS", Fields.NUMBER),
        ("UR", Fields.URL),
        ("SN", Fields.ISSN),
        ("AB", Fields.ABSTRACT),
        ("KW", Fields.KEYWORDS),
        ("PB", Fields.PUBLISHER),
    ):
        _map_first(record_dict, target, (tag,))

    if Fields.PAGES not in record_dict:
        start_page = _first_non_empty(record_dict, ("SP",))
        end_page = _first_non_empty(record_dict, ("EP",))
        if start_page is not None:
            record_dict[Fields.PAGES] = str(start_page)
            if end_page is not None:
                record_dict[Fields.PAGES] += f"--{end_page}"
    if Fields.PAGES in record_dict and str(record_dict[Fields.PAGES]).strip():
        record_dict.pop("SP", None)
        record_dict.pop("EP", None)

    if Fields.YEAR in record_dict:
        year_match = re.search(r"(?<!\d)(\d{4})(?!\d)", str(record_dict[Fields.YEAR]))
        if year_match:
            record_dict[Fields.YEAR] = year_match.group(1)
    if isinstance(record_dict.get(Fields.AUTHOR), list):
        record_dict[Fields.AUTHOR] = " and ".join(record_dict[Fields.AUTHOR])
    if isinstance(record_dict.get(Fields.KEYWORDS), list):
        record_dict[Fields.KEYWORDS] = ", ".join(record_dict[Fields.KEYWORDS])

    for control_field in ("ER", "Y2", "DB"):
        record_dict.pop(control_field, None)


class RISLoader(colrev.loader.loader.Loader):
    """Loads ris files."""

    PATTERN = r"^[A-Z0-9]{2,4} "
    NUMBERED_RECORD_PATTERN = re.compile(r"^\s*\d+\.\s*$")

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        filename: Path,
        entrytype_setter: typing.Callable = set_entrytype,
        field_mapper: typing.Callable = map_fields,
        id_labeler: typing.Callable = lambda x: x,
        unique_id_field: str = "",
        logger: logging.Logger = logging.getLogger(__name__),
        format_names: bool = False,
    ):
        """Initialize the instance."""
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
        """Get the number of records in the file."""
        count = 0
        with open(filename, encoding="utf-8") as file:
            for line in file:
                if line.startswith("TY "):
                    count += 1
        return count

    def _get_tag(self, line: str) -> str:
        """Get the tag from a line in the RIS file."""
        return line[0 : line.find(" ")].rstrip()

    def _get_content(self, line: str) -> str:
        """Get the content from a line."""
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
            if self.NUMBERED_RECORD_PATTERN.fullmatch(line):
                continue
            if re.match(self.pattern, line):
                lines.append(line)
            if line.strip() in ["", "\n"]:
                lines.append(line)
        lines.append("")
        return "\n".join(lines)

    def load_records_list(self, *, content: str = "") -> list:
        """Load ris entries.

        The resulting keys should coincide with those in the KEY_MAP
        but they can be adapted before calling the convert_to_records()
        """
        # Note : depending on the source, a specific ris_parser implementation may be selected.
        # its DEFAULT_LIST_TAGS can be extended with list fields that should be joined automatically

        if content == "":
            content = self.filename.read_text(encoding="utf-8")
            content = self._clean_text(content)

        lines = content.split("\n")
        records_list = list(r for r in self._parse_lines(lines) if r)

        return records_list

    # def apply_ris_fixes(self) -> None:
    #     """Fix common defects in RIS files"""

    #     # Error to fix: for lists of keywords, each line should start with the KW tag

    #     with open(self.filename, encoding="UTF-8") as file:
    #         lines = [line.rstrip("\n") for line in file]
    #         # add missing start tags in lists (like KW)
    #         processing_tag = ""
    #         for i, line in enumerate(lines):
    #             tag_match = re.match(r"^[A-Z][A-Z0-9]+(\s+)-", line)  # |^ER\s?|^EF\s?
    #             if tag_match:
    #                 processing_tag = tag_match.group()
    #             elif line == "":
    #                 processing_tag = ""
    #                 continue
    #             elif processing_tag == "":
    #                 continue
    #             else:
    #                 lines[i] = f"{processing_tag} {line}"

    #     with open(self.filename, "w", encoding="utf-8") as file:
    #         for line in lines:
    #             file.write(f"{line}\n")
