#! /usr/bin/env python
"""Convenience functions to load RIS files

RIS requires a mapping from the RIS_FIELDS to the standard CoLRev Fields (see CEP 002), which

- can involve merging of RIS_FIELDS (e.g. AU / author fields)
- can be conditional upon the ENTRYTYPE (e.g., publication_name: journal or booktitle)

Usage::

    import colrev.ops.load_utils_ris
    from colrev.constants import Fields, ENTRYTYPES

    # The mappings need to be adapted to the SearchSource
    entrytype_map = {
        "JOUR": ENTRYTYPES.ARTICLE,
        "CONF": ENTRYTYPES.INPROCEEDINGS,
    }
    key_map = {
        ENTRYTYPES.ARTICLE: {
            "PY": Fields.YEAR,
            "AU": Fields.AUTHOR,
            "TI": Fields.TITLE,
            "T2": Fields.JOURNAL,
            "VL": Fields.VOLUME,
            "IS": Fields.NUMBER,
            "SP": Fields.PAGES,
            "DO": Fields.DOI,
        },
        ENTRYTYPES.INPROCEEDINGS: {
            "PY": Fields.YEAR,
            "AU": Fields.AUTHOR,
            "TI": Fields.TITLE,
            "T2": Fields.BOOKTITLE,
            "DO": Fields.DOI,
            "SP": Fields.PAGES,
        },
    }

    ris_loader = colrev.ops.load_utils_ris.RISLoader(
        load_operation=load_operation,
        source=self.search_source,
        list_fields={"AU": " and "},
    )

    # Note : fixes can be applied before each of the following steps

    records = ris_loader.load_ris_records()

    for record_dict in records.values():
        ris_loader.apply_entrytype_mapping(record_dict=record_dict, entrytype_map=entrytype_map)
        ris_loader.map_keys(record_dict=record_dict, key_map=key_map)


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

import re
import typing
from pathlib import Path
from typing import TYPE_CHECKING

from colrev.constants import Colors
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.load


class NextLine(Exception):
    """NextLineException"""


class ParseError(Exception):
    """Parsing error"""


class RISLoader:

    """Loads ris files"""

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

    def __get_tag(self, line: str) -> str:
        """Get the tag from a line in the RIS file."""
        return line[0 : line.find(" ")].rstrip()

    def __get_content(self, line: str) -> str:
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
        new_value = self.__get_content(line)

        if tag in self.list_fields:
            self._add_list_value(tag, new_value)
        else:
            self._add_single_value(tag, new_value)

    def _parse_tag(self, line: str) -> dict:
        tag = self.__get_tag(line)

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

    def load_ris_records(
        self, *, content: str = "", combine_sp_ep: bool = True
    ) -> dict:
        """Load ris entries

        The resulting keys should coincide with those in the KEY_MAP
        but they can be adapted before calling the convert_to_records()"""

        # Note : depending on the source, a specific ris_parser implementation may be selected.
        # its DEFAULT_LIST_TAGS can be extended with list fiels that should be joined automatically

        if self.unique_id_field == "":
            self.load_operation.ensure_append_only(file=self.source.filename)

        if content == "":
            content = self.source.filename.read_text(encoding="utf-8")
            content = self.__clean_text(content)

        lines = content.split("\n")
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

    def apply_entrytype_mapping(
        self, *, record_dict: dict, entrytype_map: dict
    ) -> None:
        """Apply the mapping of RIS TY fields to CoLRev ENTRYTYPES"""
        if record_dict["TY"] not in entrytype_map:
            msg = f"{Colors.RED}TY={record_dict['TY']} not yet supported{Colors.END}"
            if not self.load_operation.review_manager.force_mode:
                raise NotImplementedError(msg)
            self.load_operation.review_manager.logger.error(msg)
            return

        entrytype = entrytype_map[record_dict["TY"]]
        record_dict[Fields.ENTRYTYPE] = entrytype

    def map_keys(self, *, record_dict: dict, key_map: dict) -> None:
        """Apply the mapping of RIS fields to CoLRev Fields"""
        entrytype = record_dict[Fields.ENTRYTYPE]

        # RIS-keys > standard keys
        for ris_key in list(record_dict.keys()):
            if ris_key in ["ENTRYTYPE", "ID"]:
                continue
            if ris_key not in key_map[entrytype]:
                del record_dict[ris_key]
                # print/notify: ris_key
                continue
            standard_key = key_map[entrytype][ris_key]
            record_dict[standard_key] = record_dict.pop(ris_key)
