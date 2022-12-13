#! /usr/bin/env python
"""OCR as a PDF preparation operation"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from lingua.builder import LanguageDetectorBuilder

import colrev.env.package_manager
import colrev.env.utils
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
@dataclass
class PDFCheckOCR(JsonSchemaMixin):
    """Prepare PDFs by checking and applying OCR (if necessary) based on OCRmyPDF"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.ocrmypdf_image = "jbarlow83/ocrmypdf:latest"
        pdf_prep_operation.review_manager.environment_manager.build_docker_image(
            imagename=self.ocrmypdf_image
        )

    language_detector = (
        LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
    )

    def __text_is_english(self, *, text: str) -> bool:
        # Format: ENGLISH
        confidence_values = self.language_detector.compute_language_confidence_values(
            text=text
        )
        for lang, conf in confidence_values:
            if "ENGLISH" == lang.name:
                if conf > 0.85:
                    return True
            # else:
            #     print(text)
            #     print(conf)
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

        options = f"--jobs {4}"
        # if rotate:
        #     options = options + '--rotate-pages '
        # if deskew:
        #     options = options + '--deskew '
        docker_home_path = Path("/home/docker")
        command = (
            'docker run --rm --user "$(id -u):$(id -g)" -v "'
            + str(orig_path)
            + f':/home/docker" {self.ocrmypdf_image} --force-ocr '
            + options
            + ' -l eng "'
            + str(docker_home_path / pdf_path.name)
            + '"  "'
            + str(docker_home_path / ocred_filename.name)
            + '"'
        )
        subprocess.check_output([command], stderr=subprocess.STDOUT, shell=True)

        record = colrev.record.Record(data=record_dict)
        record.add_data_provenance_note(key="file", note="pdf_processed with OCRMYPDF")
        record.data["file"] = str(ocred_filename.relative_to(review_manager.path))
        record.set_text_from_pdf(project_path=review_manager.path)

    @timeout_decorator.timeout(120, use_signals=False)
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

        # gh_issue https://github.com/geritwagner/colrev/issues/64
        # allow for other languages in this and the following if statement
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
