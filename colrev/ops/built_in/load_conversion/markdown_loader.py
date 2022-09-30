#! /usr/bin/env python
"""Load conversion of reference sections (bibliographies) in md-documents based on GROBID"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager

if TYPE_CHECKING:
    import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.LoadConversionPackageInterface)
@dataclass
class MarkdownLoader(JsonSchemaMixin):

    """Loads reference strings from text (md) files (based on GROBID)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["md"]

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ):
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:

        grobid_service = load_operation.review_manager.get_grobid_service()

        grobid_service.check_grobid_availability()
        with open(source.filename, encoding="utf8") as file:
            if source.filename.suffix == ".md":
                references = [line.rstrip() for line in file if "#" not in line[:2]]
            else:
                references = [line.rstrip() for line in file]

        data = ""
        ind = 0
        for ref in references:
            options = {}
            options["consolidateCitations"] = "0"
            options["citations"] = ref
            ret = requests.post(
                grobid_service.GROBID_URL + "/api/processCitation",
                data=options,
                headers={"Accept": "application/x-bibtex"},
            )
            ind += 1
            data = data + "\n" + ret.text.replace("{-1,", "{" + str(ind) + ",")

        records = load_operation.review_manager.dataset.load_records_dict(load_str=data)

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
