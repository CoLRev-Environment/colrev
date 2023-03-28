#! /usr/bin/env python
"""Creation of TEI as a PDF preparation operation"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
@dataclass
class TEIPDFPrep(JsonSchemaMixin):
    """Prepare PDFs by creating an annotated TEI document"""

    settings_class = colrev.env.package_manager.DefaultSettings
    TEI_PATH_RELATIVE = Path("data/.tei/")
    ci_supported: bool = False

    def __init__(
        self, *, pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep, settings: dict
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        if not pdf_prep_operation.review_manager.in_ci_environment():
            grobid_service = pdf_prep_operation.review_manager.get_grobid_service()
            grobid_service.start()
            self.tei_path = (
                pdf_prep_operation.review_manager.path / self.TEI_PATH_RELATIVE
            )
            self.tei_path.mkdir(exist_ok=True, parents=True)

    @timeout_decorator.timeout(360, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> dict:
        """Prepare the analysis of PDFs by creating a TEI (based on GROBID)"""

        if not record.data.get("file", "NA").endswith(".pdf"):
            return record.data

        if not record.get_tei_filename().is_file():
            pdf_prep_operation.review_manager.logger.debug(
                f" creating tei: {record.data['ID']}"
            )
            _ = pdf_prep_operation.review_manager.get_tei(
                pdf_path=Path(record.data["file"]),
                tei_path=record.get_tei_filename(),
            )

        return record.data


if __name__ == "__main__":
    pass
