#! /usr/bin/env python
"""Function for name formatting"""
from __future__ import annotations

import re
import typing

from colrev.constants import Fields


def split_tex_string(
    string: str, sep: str = "", strip: bool = True, filter_empty: bool = False
) -> list:
    """Split a string by a separator"""

    if sep == "":
        sep = r"[\s~]+"
        filter_empty = True
    sep_re = re.compile(sep)
    brace_level = 0
    name_start = 0
    result = []
    string_len = len(string)

    for pos, char in enumerate(string):
        if char == "{":
            brace_level += 1
        elif char == "}":
            brace_level -= 1
        elif brace_level == 0 and pos > 0:
            match = sep_re.match(string[pos:])
            if match:
                sep_len = len(match.group())
                if pos + sep_len < string_len:
                    result.append(string[name_start:pos])
                    name_start = pos + sep_len
    if name_start < string_len:
        result.append(string[name_start:])
    if strip:
        result = [part.strip() for part in result]
    if filter_empty:
        result = [part for part in result if part]
    return result


class NameParser:
    """Parse a name string"""

    def __init__(self, name: str) -> None:
        self._first: list[str] = []
        self._middle: list[str] = []
        self._prelast: list[str] = []
        self._last: list[str] = []
        self._lineage: list[str] = []
        self.parse_string(name)

    def parse_string(self, name: str) -> None:
        """Parse the name string"""
        name = name.strip()
        parts = split_tex_string(name, ",")

        if len(parts) == 3:  # "von Last, Jr, First"
            self._parse_von_last(split_tex_string(parts[0]))
            self._lineage.extend(split_tex_string(parts[1]))
            self._parse_first_middle(split_tex_string(parts[2]))
        elif len(parts) == 2:  # "von Last, First"
            self._parse_von_last(split_tex_string(parts[0]))
            self._parse_first_middle(split_tex_string(parts[1]))
        elif len(parts) == 1:  # "First von Last"
            parts = split_tex_string(name)
            first_middle, von_last = self._split_at(parts, lambda part: part.islower())
            if not von_last and first_middle:
                last = first_middle.pop()
                von_last.append(last)
            self._parse_first_middle(first_middle)
            self._parse_von_last(von_last)
        else:
            raise ValueError(f"Invalid name format: {name}")

    def _parse_first_middle(self, parts: list) -> None:
        if parts:
            self._first.append(parts[0])
            self._middle.extend(parts[1:])

    def _parse_von_last(self, parts: list) -> None:
        von, last = self._rsplit_at(parts, lambda part: part.islower())
        if von and not last:
            last.append(von.pop())
        self._prelast.extend(von)
        self._last.extend(last)

    def _split_at(self, lst: list, pred: typing.Callable) -> tuple:
        pos = next((i for i, item in enumerate(lst) if pred(item)), len(lst))
        return lst[:pos], lst[pos:]

    def _rsplit_at(self, lst: list, pred: typing.Callable) -> tuple:
        rpos = next((i for i, item in enumerate(reversed(lst)) if pred(item)), len(lst))
        pos = len(lst) - rpos
        return lst[:pos], lst[pos:]

    def _get_part_as_text(self, part_type: str) -> str:
        return " ".join(getattr(self, f"_{part_type}", []))

    def format_name(self) -> str:
        """Format the name"""

        def join(name_list: list) -> str:
            return " ".join([name for name in name_list if name])

        first = self._get_part_as_text("first")
        middle = self._get_part_as_text("middle")
        prelast = self._get_part_as_text("prelast")
        last = self._get_part_as_text("last")
        lineage = self._get_part_as_text("lineage")
        name_string = ""
        if last:
            name_string += join([prelast, last])
        if lineage:
            name_string += f", {lineage}"
        if first or middle:
            name_string += ", " + join([first, middle])
        return name_string


def parse_names(names: str) -> str:
    """Parse names"""
    if "," in names:
        return names
    name_list = re.split(r"\s+and\s+|;", names)
    formatted_names = [NameParser(name.strip()).format_name() for name in name_list]
    return " and ".join(formatted_names)


def parse_names_in_records(records_dict: dict) -> None:
    """Parse names in records

    Note: requires fields to be Fields.AUTHOR/Fields.EDITOR

    """

    for record in records_dict.values():
        if Fields.AUTHOR in record:
            record[Fields.AUTHOR] = parse_names(record[Fields.AUTHOR])
        if Fields.EDITOR in record:
            record[Fields.EDITOR] = parse_names(record[Fields.EDITOR])
