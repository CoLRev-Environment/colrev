#! /usr/bin/env python
import random

import zope.interface
from dacite import from_dict

import colrev.process
import colrev.record


@zope.interface.implementer(colrev.process.PDFPreparationEndpoint)
class CustomPDFPrepratation:
    def __init__(self, *, PDF_PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def prep_pdf(self, PDF_PREPARATION, RECORD, PAD):

        if random.random() < 0.8:
            RECORD.add_data_provenance_note(key="file", note="custom_issue_detected")
            RECORD.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )

        return RECORD.data
