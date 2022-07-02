#! /usr/bin/env python
import random

import zope.interface

from colrev_core.pdf_prep import RecordState
from colrev_core.process import PDFPreparationEndpoint


@zope.interface.implementer(PDFPreparationEndpoint)
class CustomPDFPrepratation:
    @classmethod
    def prep_pdf(cls, REVIEW_MANAGER, RECORD, PAD):

        if random.random() < 0.8:
            RECORD.add_data_provenance_hint(key="file", hint="custom_issue_detected")
            RECORD.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)

        return RECORD.data
