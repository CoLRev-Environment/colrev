#! /usr/bin/env python
"""Retrieval of PDFs from the LocalIndex"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.pdf_get

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFGetPackageInterface)
@dataclass
class LocalIndexPDFGet(JsonSchemaMixin):
    """Get PDFs from LocalIndex"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        pdf_get_operation: colrev.ops.pdf_get.PDFGet,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def get_pdf(
        self, pdf_get_operation: colrev.ops.pdf_get.PDFGet, record: colrev.record.Record
    ) -> colrev.record.Record:

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
            record.import_file(review_manager=pdf_get_operation.review_manager)

        return record


if __name__ == "__main__":
    pass
