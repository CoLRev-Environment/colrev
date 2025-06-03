#! /usr/bin/env python
"""Creation of TEI as a PDF preparation operation"""
from __future__ import annotations

from pathlib import Path
import typing
from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
from colrev.constants import Fields

if typing.TYPE_CHECKING:
    import colrev.record.record_pdf

# pylint: disable=too-few-public-methods


class GROBIDTEI(base_classes.PDFPrepPackageBaseClass):
    """Prepare PDFs by creating an annotated TEI document"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    TEI_PATH_RELATIVE = Path("data/.tei/")
    ci_supported: bool = Field(default=False)

    def __init__(
        self, *, pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep, settings: dict
    ) -> None:
        self.settings = self.settings_class(**settings)
        self.review_manager = pdf_prep_operation.review_manager

        if not pdf_prep_operation.review_manager.in_ci_environment():
            self.tei_path = (
                pdf_prep_operation.review_manager.path / self.TEI_PATH_RELATIVE
            )
            self.tei_path.mkdir(exist_ok=True, parents=True)

    def prep_pdf(
        self,
        record: colrev.record.record_pdf.PDFRecord,
        pad: int,  # pylint: disable=unused-argument
    ) -> colrev.record.record_pdf.PDFRecord:
        """Prepare the analysis of PDFs by creating a TEI (based on GROBID)"""

        if not record.data.get(Fields.FILE, "NA").endswith(".pdf"):
            return record

        if not record.get_tei_filename().is_file():
            self.review_manager.logger.debug(f" creating tei: {record.data['ID']}")
            _ = colrev.env.tei_parser.TEIParser(
                pdf_path=Path(record.data[Fields.FILE]),
                tei_path=record.get_tei_filename(),
            )

        return record
