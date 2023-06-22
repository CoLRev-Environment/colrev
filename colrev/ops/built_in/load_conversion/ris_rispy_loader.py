#! /usr/bin/env python
"""Load conversion of bib files using rispy"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import rispy
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from rispy import BaseParser
from rispy.config import LIST_TYPE_TAGS
from rispy.config import TAG_KEY_MAPPING

import colrev.env.package_manager

if TYPE_CHECKING:
    import colrev.ops.load


# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


class DefaultRISParser(BaseParser):
    """Default parser for RIS files."""

    START_TAG = "TY"
    IGNORE = ["FN", "VR", "EF"]
    PATTERN = r"^[A-Z][A-Z0-9] |^ER\s?|^EF\s?"
    DEFAULT_MAPPING = TAG_KEY_MAPPING
    DEFAULT_LIST_TAGS = LIST_TYPE_TAGS

    def get_content(self, line: str) -> str:
        "Get the content from a line."
        return line[line.find(" - ") + 2 :].strip()

    def is_header(self, line: str) -> bool:
        "Check whether the line is a header element"
        return not re.match("[A-Z0-9]+  - ", line)


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
@dataclass
class RisRispyLoader(JsonSchemaMixin):
    """Loads BibTeX files (based on rispy)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["ris"]

    ci_supported: bool = True

    __fields_to_check = {
        "title",
        "primary_title",
        "secondary_title",
        "notes_abstract",
        "note",
        "volume",
        "doi",
        "publisher",
        "number",
        "edition",
    }
    __replace_with = {
        "primary_title": "title",
        "notes_abstract": "abstract",
        "secondary_title": "journal",
        "publication_year": "year",
    }
    __reference_types = {
        "JOUR": "article",
        "JFULL": "article",
        "CONF": "inproceedings",
        "THES": "phdthesis",
        "REPT": "techreport",
        "CHAP": "inbook",
        "BOOK": "book",
    }

    __entry_fixes = {
        "article": {
            "booktitle": ["primary_title", "secondary_title", "title"],
        },
        "misc": {
            "booktitle": ["primary_title", "secondary_title", "title"],
        },
    }

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ) -> None:
        self.entries = None
        self.settings = self.settings_class.load_settings(data=settings)

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""
        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[source.get_dict()],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]

        records: dict = {}
        if source.filename.is_file():
            # Note : depending on the source, a specific ris_parser implementation may be selected.
            ris_parser = DefaultRISParser
            if hasattr(endpoint, "ris_parser"):
                ris_parser = endpoint.ris_parser
            with open(source.filename, encoding="utf-8") as ris_file:
                self.entries = rispy.load(file=ris_file, implementation=ris_parser)

            if self.entries:
                records = self.__parse_ris_file()

        records = endpoint.load_fixes(  # type: ignore
            load_operation, source=source, records=records
        )
        return records

    def __get_authors(self, entry: dict) -> list[str]:
        """Get authors"""
        keys = ["first_authors", "secondary_authors", "tertiary_authors"]
        authors = []
        for key in keys:
            try:
                authors.extend(entry[key])
            except KeyError:
                continue
        if not authors and "authors" in entry:
            return entry["authors"]
        return authors

    def __get_year(self, entry: dict) -> str:
        """Get year"""
        try:
            return entry["year"].strip("/")
        except KeyError:
            return entry["publication_year"].strip("/")

    def __get_entry_id(self, authors: list[str], year: str) -> str:
        """Get entry id, CoLRev uses 3 auther + year as ID"""
        if len(authors) >= 3:
            authors = authors[:3]
        three_author = "".join([author.rsplit(",")[0].strip() for author in authors])
        _id = f"{three_author.lower()}{year}".replace(" ", "_").strip(".")
        return _id

    def __add_entry(self, _entry: dict, key: str, record: dict) -> None:
        if key in _entry:
            val = _entry[key]
            target_key = (
                key if key not in self.__replace_with else self.__replace_with[key]
            )
            record[target_key] = val

    def __get_entry_type(self, type_of_reference: str) -> str:
        try:
            return self.__reference_types[type_of_reference]
        except KeyError:
            return "misc"

    def fix_fields_by_entry_type(
        self, entry: dict, entry_type: str, record: dict
    ) -> None:
        """Fixes some fields by entry type"""
        try:
            for key, value in self.__entry_fixes[entry_type].items():
                new_val = self.__fix_field(entry, value)
                if key not in record:
                    record[key] = new_val
        except KeyError:
            pass

    def __fix_field(self, entry: dict, value: list[str]) -> str | None:
        new_val = None
        for field in value:
            try:
                new_val = entry[field]
            except KeyError:
                continue
        return new_val

    def __parse_ris_file(self) -> dict | None:
        """Parses given ris file with rispy and convert it to bib record"""
        if not self.entries:
            return None
        records = {}
        for entry in self.entries:
            entry = dict(sorted(entry.items()))
            # colrev uses first 3 auther + year format
            authors = self.__get_authors(entry)
            year = self.__get_year(entry)
            _id = self.__get_entry_id(authors, year)

            entry_type = self.__get_entry_type(entry["type_of_reference"])
            record = {
                "ID": _id,
                "author": " and ".join(authors),
                "ENTRYTYPE": entry_type,
                "year": year,
            }
            for field in self.__fields_to_check:
                self.__add_entry(entry, field, record)
            if "starting_page" in entry and "final_page" in entry:
                record["pages"] = f"{entry['starting_page']}--{entry['final_page']}"
            elif "starting_page" in entry:
                record["pages"] = f"{entry['starting_page']}--"
            if "journal" not in record:
                new_val = self.__fix_field(
                    entry, ["secondary_title", "primary_title", "title"]
                )
                record["journal"] = new_val
            self.fix_fields_by_entry_type(entry, entry_type, record)
            records[_id] = record
        return records
