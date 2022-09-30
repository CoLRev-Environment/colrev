#! /usr/bin/env python
"""Creation of TEI as a PDF preparation operation"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import timeout_decorator
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageInterface)
@dataclass
class TEIPDFPrep(JsonSchemaMixin):
    """Prepare PDFs by creating an annotated TEI document"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self, *, pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep, settings: dict
    ) -> None:

        self.settings = from_dict(data_class=self.settings_class, data=settings)

        grobid_service = pdf_prep_operation.review_manager.get_grobid_service()
        grobid_service.start()
        Path("data/.tei").mkdir(exist_ok=True)

    @timeout_decorator.timeout(360, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> dict:

        if "file" in record.data:
            if not record.get_tei_filename().is_file():
                pdf_prep_operation.review_manager.logger.info(
                    f" creating tei: {record.data['ID']}"
                )
                _ = pdf_prep_operation.review_manager.get_tei(
                    pdf_path=Path(record.data["file"]),
                    tei_path=record.get_tei_filename(),
                )

        return record.data


if __name__ == "__main__":
    pass
