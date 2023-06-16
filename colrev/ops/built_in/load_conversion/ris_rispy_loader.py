#! /usr/bin/env python
"""Load conversion of bib files using rispy"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING

import rispy
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager

if TYPE_CHECKING:
    import colrev.ops.load


# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
@dataclass
class RisRispyLoader(JsonSchemaMixin):
    """Loads BibTeX files (based on rispy)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["ris"]

    ci_supported: bool = True

    fields_to_check = {
        "title",
        "primary_title",
        "secondary_title",
        "notes_abstract",
        "note",
        "volume",
        "doi",
        "publisher",
        "number",
    }
    replace_with = {
        "primary_title": "title",
        "notes_abstract": "abstract",
        "secondary_title": "journal",
        "publication_year": "year",
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
        records: dict = {}
        if source.filename.is_file():
            with open(source.filename, encoding="utf-8") as ris_file:
                self.entries = rispy.load(file=ris_file)
            if self.entries:
                records = self.__parse_ris_file_and_convert_to_bib()

        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[source.get_dict()],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]
        records = endpoint.load_fixes(  # type: ignore
            load_operation, source=source, records=records
        )
        return records

    def __get_entry_id(self, entry: dict) -> typing.Tuple[str, str, int]:
        try:
            authors = entry["first_authors"] + entry["secondary_authors"]
        except KeyError:
            authors = entry["authors"]
        first_three_authors = authors
        if len(authors) >= 3:
            first_three_authors = authors[:3]
        try:
            year = entry["year"].strip("/")
        except KeyError:
            year = entry["publication_year"].strip("/")
        three_author = "".join(
            [author.rsplit(",")[0].strip() for author in first_three_authors]
        )
        _id = f"{three_author.lower()}{year}"
        return _id, authors, year

    def __add_entry(self, _entry: dict, key: str, record: dict) -> None:
        if key in _entry:
            val = _entry[key]
            target_key = key if key not in self.replace_with else self.replace_with[key]
            record[target_key] = val

    def __parse_ris_file_and_convert_to_bib(self) -> dict | None:
        """Parses given ris file with rispy and convert it to bib record"""
        if not self.entries:
            return None
        records = {}
        for entry in self.entries:
            entry = dict(sorted(entry.items()))
            # colrev uses first 3 auther + year format
            _id, authors, year = self.__get_entry_id(entry)
            record = {
                "ID": _id,
                "author": " and ".join(authors),
                "ENTRYTYPE": "article",
                "year": year,
            }
            for field in self.fields_to_check:
                self.__add_entry(entry, field, record)
            if "starting_page" in entry and "final_page" in entry:
                record["pages"] = f"{entry['starting_page']}--{entry['final_page']}"
            elif "starting_page" in entry:
                record["pages"] = f"{entry['starting_page']}--"

            records[_id] = record
        return records
