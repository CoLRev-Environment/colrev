#! /usr/bin/env python
"""Template for a custom PDFPrep PackageEndpoint"""
from __future__ import annotations

import random

import zope.interface
from dacite import from_dict

import colrev.operation
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
class CustomPDFPrep:
    """Class for custom pdf-prep scripts"""

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.env.package_manager.DefaultSettings, data=settings
        )

    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> colrev.record.Record:
        """Prepare the PDF"""

        if random.random() < 0.8:  # nosec
            record.add_data_provenance_note(key="file", note="custom_issue_detected")
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )

        return record
