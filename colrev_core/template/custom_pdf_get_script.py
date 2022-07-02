#! /usr/bin/env python
import zope.interface

from colrev_core.process import PDFRetrievalEndpoint


@zope.interface.implementer(PDFRetrievalEndpoint)
class CustomPDFRetrieval:
    @classmethod
    def get_pdf(cls, REVIEW_MANAGER, RECORD):

        RECORD.data["file"] = "filepath"
        REVIEW_MANAGER.REVIEW_DATASET.import_file(record=RECORD.data)

        return RECORD
