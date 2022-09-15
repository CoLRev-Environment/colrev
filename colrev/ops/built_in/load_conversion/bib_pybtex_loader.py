#! /usr/bin/env python
from __future__ import annotations

from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.env.package_manager

if TYPE_CHECKING:
    import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


@zope.interface.implementer(colrev.env.package_manager.LoadConversionPackageInterface)
class BibPybtexLoader:
    """Loads BibTeX files (based on pybtex)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["bib"]

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ):
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def __general_load_fixes(self, records):

        return records

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ):
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
        if source.source_name in load_operation.search_sources.packages:
            search_source_package = load_operation.search_sources.packages[
                source.source_name
            ]
            records = search_source_package.load_fixes(
                self, source=source, records=records
            )
        else:
            load_operation.review_manager.logger.info(
                "No custom source load_fixes for %s", source.source_name
            )

        return records


if __name__ == "__main__":
    pass
