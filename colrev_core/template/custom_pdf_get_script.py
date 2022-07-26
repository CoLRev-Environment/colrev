#! /usr/bin/env python
import zope.interface
from dacite import from_dict

from colrev_core.process import DefaultSettings
from colrev_core.process import PDFRetrievalEndpoint


@zope.interface.implementer(PDFRetrievalEndpoint)
class CustomPDFRetrieval:
    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def get_pdf(self, PDF_RETRIEVAL, RECORD):

        RECORD.data["file"] = "filepath"
        PDF_RETRIEVAL.REVIEW_MANAGER.REVIEW_DATASET.import_file(record=RECORD.data)

        return RECORD
