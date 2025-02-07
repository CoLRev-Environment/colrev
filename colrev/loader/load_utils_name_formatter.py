#! /usr/bin/env python
"""Convenience functions for name formatting"""
from __future__ import annotations

import re

whitespace_re = re.compile(r"(\s)")


def split_tex_string(string, sep=None, strip=True, filter_empty=False):
    if sep is None:
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
    def __init__(self, name: str):
        self._first = []
        self._middle = []
        self._prelast = []
        self._last = []
        self._lineage = []
        self.parse_string(name)

    def parse_string(self, name: str):
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

    def _parse_first_middle(self, parts):
        if parts:
            self._first.append(parts[0])
            self._middle.extend(parts[1:])

    def _parse_von_last(self, parts):
        von, last = self._rsplit_at(parts, lambda part: part.islower())
        if von and not last:
            last.append(von.pop())
        self._prelast.extend(von)
        self._last.extend(last)

    def _split_at(self, lst, pred):
        pos = next((i for i, item in enumerate(lst) if pred(item)), len(lst))
        return lst[:pos], lst[pos:]

    def _rsplit_at(self, lst, pred):
        rpos = next((i for i, item in enumerate(reversed(lst)) if pred(item)), len(lst))
        pos = len(lst) - rpos
        return lst[:pos], lst[pos:]

    def get_part_as_text(self, part_type: str) -> str:
        return " ".join(getattr(self, f"_{part_type}", []))

    def format_name(self) -> str:
        def join(name_list):
            return " ".join([name for name in name_list if name])

        first = self.get_part_as_text("first")
        middle = self.get_part_as_text("middle")
        prelast = self.get_part_as_text("prelast")
        last = self.get_part_as_text("last")
        lineage = self.get_part_as_text("lineage")
        name_string = ""
        if last:
            name_string += join([prelast, last])
        if lineage:
            name_string += f", {lineage}"
        if first or middle:
            name_string += ", " + join([first, middle])
        return name_string


def parse_names(names: str) -> str:
    if "," in names:
        return names
    name_list = re.split(r"\s+and\s+|;", names)
    formatted_names = [NameParser(name.strip()).format_name() for name in name_list]
    return " and ".join(formatted_names)
