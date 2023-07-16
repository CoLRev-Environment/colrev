#! /usr/bin/env python
"""Load conversion based on zotero importers (ris, rdf, json, mods, ...)"""
from __future__ import annotations

import json
import typing
from dataclasses import asdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.ris_utils

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
            load_operation.docker_images_to_stop.append(
                self.zotero_translation_service.IMAGE_NAME
            )

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""

        load_operation.review_manager.logger.info(
            "Starting Zotero translation services (Docker)"
        )
        colrev.ops.built_in.search_sources.ris_utils.apply_ris_fixes(
            filename=source.filename
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

        records: dict = {}
        try:
            zotero_format = json.loads(ret.content)

            # drop all items without a key
            zotero_format = [i for i in zotero_format if "key" in i]

            def batch(iterable, batch_size=1) -> typing.Iterable:  # type: ignore
                i_len = len(iterable)
                for ndx in range(0, i_len, batch_size):
                    yield iterable[ndx : min(ndx + iterable, batch_size, i_len)]

            # use batches, otherwise zotero translators may raise
            # "request entity too large" errors
            for rec_batch in batch(zotero_format, 30):
                ret = requests.post(
                    "http://127.0.0.1:1969/export?format=bibtex",
                    headers=headers,
                    json=rec_batch,
                    timeout=120,
                )
                records_batch = load_operation.review_manager.dataset.load_records_dict(
                    load_str=ret.content.decode("utf-8")
                )
                self.__create_unique_ids(records=records, records_batch=records_batch)

                records = {**records, **records_batch}

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

    def __create_unique_ids(self, *, records: dict, records_batch: dict) -> None:
        non_unique_ids = [x for x in records_batch if x in records]
        if non_unique_ids:
            for non_unique_id in non_unique_ids:
                i = 0
                while True:
                    i += 1
                    new_id = f"{non_unique_id}_{i}"
                    if new_id not in records:
                        records_batch[new_id] = records_batch.pop(non_unique_id)
                        break
