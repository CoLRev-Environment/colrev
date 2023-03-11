#! /usr/bin/env python
"""Retrieval of PDFs from the LocalIndex"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.record

# pylint: disable=duplicate-code
if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_get

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFGetPackageEndpointInterface)
@dataclass
class LocalIndexPDFGet(JsonSchemaMixin):
    """Get PDFs from LocalIndex"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_get_operation: colrev.ops.pdf_get.PDFGet,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def get_pdf(
        self, pdf_get_operation: colrev.ops.pdf_get.PDFGet, record: colrev.record.Record
    ) -> colrev.record.Record:
        """Get PDFs from the local-index"""

        local_index = pdf_get_operation.review_manager.get_local_index()

        try:
            retrieved_record = local_index.retrieve(
                record_dict=record.data, include_file=True
            )
        except colrev_exceptions.RecordNotInIndexException:
            return record

        if "file" in retrieved_record:
            record.update_field(
                key="file", value=str(retrieved_record["file"]), source="local_index"
            )
            pdf_get_operation.import_file(record=record)
            if "fulltext" in retrieved_record:
                try:
                    record.get_tei_filename().write_text(retrieved_record["fulltext"])
                except FileNotFoundError:
                    pass
                del retrieved_record["fulltext"]
            else:
                tei_ext_path = Path(
                    retrieved_record["file"]
                    .replace("pdfs/", ".tei/")
                    .replace(".pdf", ".tei.xml")
                )
                if tei_ext_path.is_file():
                    new_path = record.get_tei_filename()
                    new_path.resolve().parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy(tei_ext_path, new_path)

        return record


if __name__ == "__main__":
    pass
