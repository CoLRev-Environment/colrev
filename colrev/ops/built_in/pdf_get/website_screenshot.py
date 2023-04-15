#! /usr/bin/env python
"""Creation of screenshots (PDFs) for online ENTRYTYPES"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record

# pylint: disable=duplicate-code
if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_get

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFGetPackageEndpointInterface)
@dataclass
class WebsiteScreenshot(JsonSchemaMixin):
    """Get PDFs from website screenshot (for "online" ENTRYTYPES)"""

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
        """Get a PDF of the website (screenshot)"""

        if record.data["ENTRYTYPE"] != "online":
            return record

        screenshot_service = pdf_get_operation.review_manager.get_screenshot_service()
        screenshot_service.start_screenshot_service()

        pdf_filepath = pdf_get_operation.review_manager.PDF_DIR_RELATIVE / Path(
            f"{record.data['ID']}.pdf"
        )
        record = screenshot_service.add_screenshot(
            record=record, pdf_filepath=pdf_filepath
        )

        if "file" in record.data:
            pdf_get_operation.import_file(record=record)

        return record


if __name__ == "__main__":
    pass
