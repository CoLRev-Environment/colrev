#! /usr/bin/env python
from __future__ import annotations

from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.process

if TYPE_CHECKING:
    import colrev.ops.pdf_get


@zope.interface.implementer(colrev.process.PDFGetEndpoint)
class CustomPDFGet:
    def __init__(
        self, *, pdf_get_operation: colrev.ops.pdf_get.PDFGet, settings: dict
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def get_pdf(
        self, pdf_get_operation: colrev.ops.pdf_get.PDFGet, record: colrev.record.Record
    ) -> colrev.record.Record:

        record.data["file"] = "filepath"
        pdf_get_operation.review_manager.dataset.import_file(record=record.data)

        return record
