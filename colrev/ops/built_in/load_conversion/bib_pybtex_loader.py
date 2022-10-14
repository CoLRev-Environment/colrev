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
        """Load records from the source"""
        records = {}
        # gh_issue https://github.com/geritwagner/colrev/issues/80
        # implement set_incremental_ids() and fix_keys() (text-file replacements)
        # here (pybtex does not load records with identical IDs /
        # fields with keys containing white spaces)
        if source.filename.is_file():
            with open(source.filename, encoding="utf8") as bibtex_file:
                records = load_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
        records = self.__general_load_fixes(records)

        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[source.get_dict()],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]

        records = endpoint.load_fixes(self, source=source, records=records)  # type: ignore

        return records


if __name__ == "__main__":
    pass
