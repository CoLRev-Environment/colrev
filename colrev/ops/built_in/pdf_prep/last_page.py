#! /usr/bin/env python
"""Last-page removal as a PDF preparation operation"""
from __future__ import annotations

import shutil
import typing
from dataclasses import dataclass
from pathlib import Path

import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from PyPDF2 import PdfFileReader

import colrev.env.package_manager
import colrev.env.utils
import colrev.record

# pylint: disable=duplicate-code

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
@dataclass
class PDFLastPage(JsonSchemaMixin):
    """Prepare PDFs by removing unnecessary last pages (e.g. copyright notices, cited-by infos)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> dict:
        """Prepare the PDF by removing additional materials (if any)"""

        if not record.data["file"].endswith(".pdf"):
            return record.data

        local_index = pdf_prep_operation.review_manager.get_local_index()
        lp_path = local_index.local_environment_path / Path(".lastpages")
        lp_path.mkdir(exist_ok=True)

        def __get_last_pages(*, pdf: str) -> typing.List[int]:
            last_pages: typing.List[int] = []
            try:
                pdf_reader = PdfFileReader(str(pdf), strict=False)
            except ValueError:
                return last_pages

            last_page_nr = len(pdf_reader.pages) - 1

            last_page_average_hash_16 = colrev.qm.colrev_pdf_id.get_pdf_hash(
                pdf_path=Path(pdf),
                page_nr=last_page_nr + 1,
                hash_size=16,
            )

            if last_page_nr == 1:
                return last_pages

            # Note : to generate hashes from a directory containing single-page PDFs:
            # colrev pdf-prep --pdf_hash path
            last_page_hashes = [
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffff83ff83ff",
                "ffff80038007ffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "c3fbc003c003ffc3ff83ffc3ffffffffffffffffffffffffffffffffffffffff",
                "ffff80038007ffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "ffff80038001ffff7fff7fff7fff7fff7fff7fff7fff7fffffffffffffffffff",
                "ffff80008003ffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "ffff80038007ffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "ffff80018001ffffffffffffffffffffffffffffffffffffffffffffffffffff",
            ]

            if str(last_page_average_hash_16) in last_page_hashes:
                last_pages.append(last_page_nr)

            res = pdf_reader.getPage(last_page_nr).extract_text()
            last_page_text = res.replace(" ", "").replace("\n", "").lower()

            # ME Sharpe last page
            if (
                "propertyofm.e.sharpeinc.anditscontentmayno"
                + "tbecopiedoremailedtomultiplesi"
                + "tesorpostedtoalistservwithoutthecopyrightholder"
                in last_page_text
            ):
                last_pages.append(last_page_nr)

            # CAIS last page / editorial board
            if all(
                x in last_page_text
                for x in [
                    "caisadvisoryboard",
                    "caiseditorialboard",
                    "caissenioreditors",
                ]
            ):
                last_pages.append(last_page_nr)

            return list(set(last_pages))

        last_pages = __get_last_pages(pdf=record.data["file"])
        if not last_pages:
            return record.data
        if last_pages:
            original = pdf_prep_operation.review_manager.path / Path(
                record.data["file"]
            )
            file_copy = pdf_prep_operation.review_manager.path / Path(
                record.data["file"].replace(".pdf", "_wo_lp.pdf")
            )
            shutil.copy(original, file_copy)

            record.extract_pages(
                pages=last_pages,
                project_path=pdf_prep_operation.review_manager.path,
                save_to_path=lp_path,
            )
            pdf_prep_operation.review_manager.report_logger.info(
                f'removed last page for ({record.data["ID"]})'
            )
        return record.data


if __name__ == "__main__":
    pass
