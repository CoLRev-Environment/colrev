#! /usr/bin/env python
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.process
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.pdf_prep


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageInterface)
class CustomPDFPrep:
    def __init__(
        self, *, pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep, settings: dict
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.env.package_manager.DefaultSettings, data=settings
        )

    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,
    ) -> colrev.record.Record:

        if random.random() < 0.8:
            record.add_data_provenance_note(key="file", note="custom_issue_detected")
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )

        return record
