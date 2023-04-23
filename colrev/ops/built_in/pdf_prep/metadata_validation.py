#! /usr/bin/env python
"""Metadata validation as a PDF preparation operation"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
@dataclass
class PDFMetadataValidation(JsonSchemaMixin):
    """Prepare PDFs by validating it against its associated metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def validates_based_on_metadata(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.Record,
    ) -> dict:
        """Validates the PDF based on the metadata (record)"""

        validation_info = {"msgs": [], "pdf_prep_hints": [], "validates": True}

        if "text_from_pdf" not in record.data:
            record.set_text_from_pdf(project_path=review_manager.path)

        text = record.data["text_from_pdf"]
        text = text.replace(" ", "").replace("\n", "").lower()
        text = colrev.env.utils.remove_accents(input_str=text)
        text = re.sub("[^a-zA-Z ]+", "", text)

        title_words = re.sub("[^a-zA-Z ]+", "", record.data["title"]).lower().split()

        match_count = 0
        for title_word in title_words:
            if title_word in text:
                match_count += 1

        if "title" not in record.data or len(title_words) == 0:
            validation_info["msgs"].append(  # type: ignore
                f"{record.data['ID']}: title not in record"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "title_not_in_record"
            )
            validation_info["validates"] = False
            return validation_info
        if "author" not in record.data:
            validation_info["msgs"].append(  # type: ignore
                f"{record.data['ID']}: author not in record"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "author_not_in_record"
            )
            validation_info["validates"] = False
            return validation_info

        if match_count / len(title_words) < 0.9:
            validation_info["msgs"].append(  # type: ignore
                f"{record.data['ID']}: title not found in first pages"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "title_not_in_first_pages"
            )
            validation_info["validates"] = False

        text = text.replace("ue", "u").replace("ae", "a").replace("oe", "o")

        # Editorials often have no author in the PDF (or on the last page)
        if "editorial" not in title_words:
            match_count = 0
            for author_name in record.data.get("author", "").split(" and "):
                author_name = author_name.split(",")[0].lower().replace(" ", "")
                author_name = colrev.env.utils.remove_accents(input_str=author_name)
                author_name = (
                    author_name.replace("ue", "u").replace("ae", "a").replace("oe", "o")
                )
                author_name = re.sub("[^a-zA-Z ]+", "", author_name)
                if author_name in text:
                    match_count += 1

            if match_count / len(record.data.get("author", "").split(" and ")) < 0.8:
                validation_info["msgs"].append(  # type: ignore
                    f"{record.data['file']}: author not found in first pages"
                )
                validation_info["pdf_prep_hints"].append(  # type: ignore
                    "author_not_in_first_pages"
                )
                validation_info["validates"] = False

        return validation_info

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int = 40,  # pylint: disable=unused-argument
    ) -> dict:
        """Prepare the PDF by validating it against the metadata (record)"""

        if colrev.record.RecordState.pdf_imported != record.data.get(
            "colrev_status", "NA"
        ):
            return record.data

        if not record.data["file"].endswith(".pdf"):
            return record.data

        local_index = pdf_prep_operation.review_manager.get_local_index()

        try:
            retrieved_record = local_index.retrieve(record_dict=record.data)

            pdf_path = pdf_prep_operation.review_manager.path / Path(
                record.data["file"]
            )
            current_cpid = record.get_colrev_pdf_id(pdf_path=pdf_path)

            if "colrev_pdf_id" in retrieved_record:
                if retrieved_record["colrev_pdf_id"] == str(current_cpid):
                    # pdf_prep_operation.review_manager.logger.debug(
                    #     "validated pdf metadata based on local_index "
                    #     f"({record.data['ID']})"
                    # )
                    return record.data
                pdf_prep_operation.review_manager.logger.debug(
                    "colrev_pdf_ids not matching"
                )
        except colrev_exceptions.RecordNotInIndexException:
            pass

        validation_info = self.validates_based_on_metadata(
            review_manager=pdf_prep_operation.review_manager, record=record
        )
        if not validation_info["validates"]:
            for msg in validation_info["msgs"]:
                pdf_prep_operation.review_manager.report_logger.error(msg)

            notes = ",".join(validation_info["pdf_prep_hints"])
            record.add_data_provenance_note(key="file", note=notes)
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )

        return record.data


if __name__ == "__main__":
    pass
