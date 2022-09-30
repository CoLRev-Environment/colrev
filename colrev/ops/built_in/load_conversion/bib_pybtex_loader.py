#! /usr/bin/env python
"""Load conversion of bib files using pybtex"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
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
class BibPybtexLoader(JsonSchemaMixin):

    """Loads BibTeX files (based on pybtex)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["bib"]

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def __general_load_fixes(self, records: dict) -> dict:

        return records

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        records = {}
        # TODO : implement set_incremental_ids() and fix_keys() (text-file replacements)
        # here (pybtex does not load records with identical IDs /
        # fields with keys containing white spaces)
        if source.filename.is_file():
            with open(source.filename, encoding="utf8") as bibtex_file:
                records = load_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
        records = self.__general_load_fixes(records)
        if source.endpoint in load_operation.search_sources.packages:
            search_source_package = load_operation.search_sources.packages[
                source.endpoint
            ]
            records = search_source_package.load_fixes(
                self, source=source, records=records
            )
        else:
            load_operation.review_manager.logger.info(
                "No custom source load_fixes for %s", source.endpoint
            )

        return records


if __name__ == "__main__":
    pass
