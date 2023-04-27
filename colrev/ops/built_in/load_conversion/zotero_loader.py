#! /usr/bin/env python
"""Load conversion based on zotero importers (ris, rdf, json, mods, ...)"""
from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
@dataclass
class ZoteroTranslationLoader(JsonSchemaMixin):

    """Loads bibliography files (based on Zotero).
    Supports ris, rdf, json, mods, xml, marc, txt"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    supported_extensions = ["ris", "rdf", "json", "mods", "xml", "marc", "txt"]

    def __init__(self, *, load_operation: colrev.ops.load.Load, settings: dict):
        self.settings = self.settings_class.load_settings(data=settings)

        if not load_operation.review_manager.in_ci_environment():
            self.zotero_translation_service = (
                load_operation.review_manager.get_zotero_translation_service()
            )

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""

        load_operation.review_manager.logger.info(
            "Starting Zotero translation services (Docker)"
        )
        self.zotero_translation_service.start()

        # pylint: disable=consider-using-with

        files = {"file": open(source.filename, "rb")}
        headers = {"Content-type": "text/plain"}
        ret = requests.post(
            "http://127.0.0.1:1969/import", headers=headers, files=files, timeout=30
        )

        headers = {"Content-type": "application/json"}
        if ret.content.decode("utf-8") == "No suitable translators found":
            raise colrev_exceptions.ImportException(
                "Zotero translators: No suitable import translators found"
            )

        try:
            zotero_format = json.loads(ret.content)
            ret = requests.post(
                "http://127.0.0.1:1969/export?format=bibtex",
                headers=headers,
                json=zotero_format,
                timeout=60,
            )
            records = load_operation.review_manager.dataset.load_records_dict(
                load_str=ret.content.decode("utf-8")
            )

        except Exception as exc:
            raise colrev_exceptions.ImportException(
                f"Zotero import translators failed ({exc})"
            )

        self.zotero_translation_service.stop()

        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[asdict(source)],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]

        records = endpoint.load_fixes(  # type: ignore
            load_operation, source=source, records=records
        )
        return records


if __name__ == "__main__":
    pass
