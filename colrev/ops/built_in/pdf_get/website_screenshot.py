#! /usr/bin/env python
"""Creation of screenshots (PDFs) for online ENTRYTYPES"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.pdf_get

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFGetPackageEndpointInterface)
@dataclass
class WebsiteScreenshot(JsonSchemaMixin):
    """Get PDFs from webisite screenshot (for "online" ENTRYTYPES)"""

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

        screenshot_service = pdf_get_operation.review_manager.get_screenshot_service()

        if "online" == record.data["ENTRYTYPE"]:
            screenshot_service.start_screenshot_service()

            pdf_filepath = pdf_get_operation.review_manager.PDF_DIR_RELATIVE / Path(
                f"{record.data['ID']}.pdf"
            )
            record = screenshot_service.add_screenshot(
                record=record, pdf_filepath=pdf_filepath
            )

            if "file" in record.data:
                record.import_file(review_manager=pdf_get_operation.review_manager)

        return record


if __name__ == "__main__":
    pass
