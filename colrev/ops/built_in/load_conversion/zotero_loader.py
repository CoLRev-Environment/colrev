#! /usr/bin/env python
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import requests
import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions

if TYPE_CHECKING:
    import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.LoadConversionPackageInterface)
class ZoteroTranslationLoader:
    """Loads bibliography files (based on pandas).
    Supports ris, rdf, json, mods, xml, marc, txt"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["ris", "rdf", "json", "mods", "xml", "marc", "txt"]

    def __init__(self, *, load_operation: colrev.ops.load.Load, settings: dict):

        self.settings = from_dict(data_class=self.settings_class, data=settings)

        self.zotero_translation_service = (
            load_operation.review_manager.get_zotero_translation_service()
        )
        self.zotero_translation_service.start_zotero_translators(
            startup_without_waiting=True
        )

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ):

        self.zotero_translation_service.start_zotero_translators()
        # pylint: disable=consider-using-with
        files = {"file": open(source.filename, "rb")}
        headers = {"Content-type": "text/plain"}
        ret = requests.post(
            "http://127.0.0.1:1969/import", headers=headers, files=files
        )
        headers = {"Content-type": "application/json"}
        if "No suitable translators found" == ret.content.decode("utf-8"):
            raise colrev_exceptions.ImportException(
                "Zotero translators: No suitable import translators found"
            )

        try:
            zotero_format = json.loads(ret.content)
            ret = requests.post(
                "http://127.0.0.1:1969/export?format=bibtex",
                headers=headers,
                json=zotero_format,
            )
            records = load_operation.review_manager.dataset.load_records_dict(
                load_str=ret.content.decode("utf-8")
            )

        except Exception as exc:
            raise colrev_exceptions.ImportException(
                f"Zotero import translators failed ({exc})"
            )

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
