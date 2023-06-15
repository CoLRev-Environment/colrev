#! /usr/bin/env python
"""Load conversion of bib files using rispy"""
from __future__ import annotations

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

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""
        records = {}
        if source.filename.is_file():
            records = self.__parse_ris_file_and_convert_to_bib(source)
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

    def __parse_ris_file_and_convert_to_bib(
        self, source: colrev.settings.SearchSource
    ) -> dict:
        """Parses given ris file with rispy and convert it to bib record"""

        def add_entry(_entry: dict, key: str, _record: dict) -> None:
            if key in _entry:
                _record[key] = _entry[key]

        with open(source.filename, encoding="utf-8") as ris_file:
            entries = rispy.load(file=ris_file)

        records = {}
        for entry in entries:
            print(entry)
            # colrev uses first 3 auther + year format
            try:
                authors = entry["authors"]
            except KeyError:
                authors = entry["first_authors"] + entry["secondary_authors"]
            first_three_authors = authors
            if len(authors) >= 3:
                first_three_authors = authors[:3]
            try:
                year = entry["year"]
            except KeyError:
                year = entry["publication_year"].strip("/")
            three_author = "".join(
                [author.rsplit(",")[0].strip() for author in first_three_authors]
            )
            _id = f"{three_author.lower()}{year}"
            record = {
                "ID": _id,
                "author": " and ".join(authors),
                "ENTRYTYPE": "article",
            }
            fields_to_check = [
                "title",
                "primary_title",
                "journal",
                "volume",
                "year",
                "doi",
                "publisher",
            ]
            for field in fields_to_check:
                add_entry(entry, field, record)
            if "starting_page" in entry and "final_page" in entry:
                record["pages"] = f"{entry['starting_page']}--{entry['final_page']}"
            records[_id] = record
        return records
