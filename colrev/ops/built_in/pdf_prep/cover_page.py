#! /usr/bin/env python
"""Cover-page removal as a PDF preparation operation"""
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
import colrev.qm.colrev_pdf_id
import colrev.record

# pylint: disable=duplicate-code


if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
@dataclass
class PDFCoverPage(JsonSchemaMixin):
    """Prepare PDFs by removing unnecessary cover pages (e.g. researchgate, publishers)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.review_manager = pdf_prep_operation.review_manager

    def __check_scholarworks_first_page(self, *, page0: str, coverpages: list) -> None:
        if "followthisandadditionalworksat:https://scholarworks" in page0:
            coverpages.append(0)

    def __check_researchgate_first_page(self, *, page0: str, coverpages: list) -> None:
        if (
            "discussions,stats,andauthorprofilesforthispublicationat:"
            + "https://www.researchgate.net/publication"
            in page0
            or "discussions,stats,andauthorproﬁlesforthispublicationat:"
            + "https://www.researchgate.net/publication"
            in page0
        ):
            coverpages.append(0)

    def __check_jstor_first_page(self, *, page0: str, coverpages: list) -> None:
        if (
            "pleasecontactsupport@jstor.org.youruseofthejstorarchiveindicatesy"
            + "ouracceptanceoftheterms&conditionsofuse"
            in page0
            or "formoreinformationregardingjstor,pleasecontactsupport@jstor.org"
            in page0
        ):
            coverpages.append(0)

    def __check_emerald_first_page(self, *, page0: str, coverpages: list) -> None:
        if (
            "emeraldisbothcounter4andtransfercompliant.theorganizationisapartnero"
            "fthecommitteeonpublicationethics(cope)andalsoworkswithporticoandthe"
            "lockssinitiativefordigitalarchivepreservation.*relatedcontentand"
            "downloadinformationcorrectattimeofdownload" in page0
        ):
            coverpages.append(0)

    def __check_informs_first_page(
        self, *, page0: str, page1: str, coverpages: list
    ) -> None:
        if (
            "thisarticlewasdownloadedby" in page0
            and "fulltermsandconditionsofuse:" in page0
        ):
            coverpages.append(0)
        if (
            "thisarticlemaybeusedonlyforthepurposesofresearch" in page0
            and "abstract" not in page0
            and "keywords" not in page0
            and "abstract" in page1
            and "keywords" in page1
        ):
            coverpages.append(0)

    def __check_ais_first_page(self, *, page0: str, coverpages: list) -> None:
        if (
            "associationforinformationsystemsaiselectroniclibrary(aisel)" in page0
            and "abstract" not in page0
            and "keywords" not in page0
        ):
            coverpages.append(0)

    def __check_tandf_first_page(
        self, *, page0: str, page1: str, coverpages: list
    ) -> None:
        if ("pleasescrolldownforarticle" in page0) or ("viewrelatedarticles" in page0):
            if "abstract" not in page0 and "keywords" not in page0:
                coverpages.append(0)
                if (
                    "terms-and-conditions" in page1
                    and "abstract" not in page1
                    and "keywords" not in page1
                ):
                    coverpages.append(1)

    def __get_coverpages(self, *, pdf: str) -> typing.List[int]:
        coverpages: typing.List[int] = []

        try:
            pdf_reader = PdfFileReader(str(pdf), strict=False)
        except ValueError:
            return coverpages

        if len(pdf_reader.pages) == 1:
            return coverpages

        first_page_average_hash_16 = colrev.qm.colrev_pdf_id.get_pdf_hash(
            pdf_path=Path(pdf),
            page_nr=1,
            hash_size=16,
        )

        # Note : to generate hashes from a directory containing single-page PDFs:
        # colrev pdf-prep --get_hashes path
        first_page_hashes = [
            "ffff83ff81ff81ffc3ff803f81ff80ffc03fffffffffffffffff96ff9fffffff",
            "ffffffffc0ffc781c007c007cfffc7ffffffffffffffc03fc007c003c827ffff",
            "84ff847ffeff83ff800783ff801f800180038fffffffffffbfff8007bffff83f",
            "83ff03ff03ff83ffffff807f807f9fff87ffffffffffffffffff809fbfffffff",
            "ffffffffc0ffc781c03fc01fffffffffffffffffffffc03fc01fc003ffffffff",
            "ffffffffc0ffc781c007c007cfffc7ffffffffffffffc03fc007c003ce27ffff",
            "ffffe7ffe3ffc3fffeff802780ff8001c01fffffffffffffffff80079ffffe3f",
            "ffffffffc0ffc781c00fc00fc0ffc7ffffffffffffffc03fc007c003cf27ffff",
            "ffffffffc0ffc781c007c003cfffcfffffffffffffffc03fc003c003cc27ffff",
            "ffffe7ffe3ffc3ffffff80e780ff80018001ffffffffffffffff93ff83ff9fff",
        ]

        if str(first_page_average_hash_16) in first_page_hashes:
            coverpages.append(0)

        res = pdf_reader.getPage(0).extract_text()
        page0 = res.replace(" ", "").replace("\n", "").lower()

        res = pdf_reader.getPage(1).extract_text()
        page1 = res.replace(" ", "").replace("\n", "").lower()

        # input(page0)

        self.__check_scholarworks_first_page(page0=page0, coverpages=coverpages)
        self.__check_researchgate_first_page(page0=page0, coverpages=coverpages)
        self.__check_jstor_first_page(page0=page0, coverpages=coverpages)
        self.__check_emerald_first_page(page0=page0, coverpages=coverpages)
        self.__check_informs_first_page(page0=page0, page1=page1, coverpages=coverpages)
        self.__check_ais_first_page(page0=page0, coverpages=coverpages)
        self.__check_tandf_first_page(page0=page0, page1=page1, coverpages=coverpages)

        return list(set(coverpages))

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> dict:
        """Prepare the PDF by removing coverpages (if any)"""

        if not record.data["file"].endswith(".pdf"):
            return record.data

        local_index = pdf_prep_operation.review_manager.get_local_index()
        cp_path = local_index.local_environment_path / Path(".coverpages")
        cp_path.mkdir(exist_ok=True)

        coverpages = self.__get_coverpages(pdf=record.data["file"])
        if not coverpages:
            return record.data
        if coverpages:
            original = pdf_prep_operation.review_manager.path / Path(
                record.data["file"]
            )
            file_copy = pdf_prep_operation.review_manager.path / Path(
                record.data["file"].replace(".pdf", "_wo_cp.pdf")
            )
            shutil.copy(original, file_copy)
            record.extract_pages(
                pages=coverpages,
                project_path=pdf_prep_operation.review_manager.path,
                save_to_path=cp_path,
            )
            pdf_prep_operation.review_manager.report_logger.info(
                f'removed cover page for ({record.data["ID"]})'
            )
        return record.data


if __name__ == "__main__":
    pass
