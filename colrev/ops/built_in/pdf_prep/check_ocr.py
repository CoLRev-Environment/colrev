#! /usr/bin/env python
"""OCR as a PDF preparation operation"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.language_service
import colrev.env.package_manager
import colrev.env.utils
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
@dataclass
class PDFCheckOCR(JsonSchemaMixin):
    """Prepare PDFs by checking and applying OCR (if necessary) based on OCRmyPDF"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        if not pdf_prep_operation.review_manager.in_ci_environment():
            self.ocrmypdf_image = "jbarlow83/ocrmypdf:latest"
            pdf_prep_operation.review_manager.environment_manager.build_docker_image(
                imagename=self.ocrmypdf_image
            )
        self.language_service = colrev.env.language_service.LanguageService()

    def __text_is_english(self, *, text: str) -> bool:
        # Format: ENGLISH
        confidence_values = self.language_service.compute_language_confidence_values(
            text=text
        )
        lang, conf = confidence_values.pop(0)
        if lang == "eng":
            if conf > 0.1:
                return True

        return False

    def __apply_ocr(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record_dict: dict,
        pad: int,  # pylint: disable=unused-argument
    ) -> None:
        pdf_path = review_manager.path / Path(record_dict["file"])
        ocred_filename = Path(str(pdf_path).replace(".pdf", "_ocr.pdf"))

        orig_path = (
            pdf_path.parents[0] if pdf_path.is_file() else review_manager.pdf_dir
        )

        # options = ""
        # if rotate:
        #     options = options + '--rotate-pages '
        # if deskew:
        #     options = options + '--deskew '
        docker_home_path = Path("/home/docker")

        command = [
            "docker",
            "run",
            "--rm",
            "--user",
            # "$(id -u):$(id -g)",
            f"{os.geteuid()}:{os.getegid()}",
            "-v",
            f"{orig_path}:/home/docker",
            self.ocrmypdf_image,
            "--force-ocr",
            # options,
            "--jobs",
            "4",
            "-l",
            "eng",
            str(docker_home_path / pdf_path.name),
            str(docker_home_path / ocred_filename.name),
        ]

        with subprocess.Popen(
            command, stdout=subprocess.PIPE, shell=False
        ) as ocr_process:
            ocr_process.wait()

        record = colrev.record.Record(data=record_dict)
        record.add_data_provenance_note(key="file", note="pdf_processed with OCRMYPDF")
        record.data["file"] = str(ocred_filename.relative_to(review_manager.path))
        record.set_text_from_pdf(project_path=review_manager.path)

    @timeout_decorator.timeout(300, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,
    ) -> dict:
        """Prepare the PDF by checking/applying OCR"""

        if colrev.record.RecordState.pdf_imported != record.data.get(
            "colrev_status", "NA"
        ):
            return record.data

        if not record.data["file"].endswith(".pdf"):
            return record.data

        # We may allow for other languages in this and the following if statement
        if not self.__text_is_english(text=record.data["text_from_pdf"]):
            pdf_prep_operation.review_manager.report_logger.info(
                f'apply_ocr({record.data["ID"]})'
            )
            self.__apply_ocr(
                review_manager=pdf_prep_operation.review_manager,
                record_dict=record.data,
                pad=pad,
            )

        if not self.__text_is_english(text=record.data["text_from_pdf"]):
            msg = (
                f'{record.data["ID"]}'.ljust(pad, " ")
                + "Validation error (OCR problems)"
            )
            pdf_prep_operation.review_manager.report_logger.error(msg)

        if not self.__text_is_english(text=record.data["text_from_pdf"]):
            msg = (
                f'{record.data["ID"]}'.ljust(pad, " ")
                + "Validation error (Language not English)"
            )
            pdf_prep_operation.review_manager.report_logger.error(msg)
            record.add_data_provenance_note(key="file", note="pdf_language_not_english")
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )
        return record.data


if __name__ == "__main__":
    pass
