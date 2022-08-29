#! /usr/bin/env python
import zope.interface
from dacite import from_dict

import colrev.process


@zope.interface.implementer(colrev.process.PDFRetrievalEndpoint)
class CustomPDFRetrieval:
    def __init__(self, *, PDF_GET, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def get_pdf(self, PDF_RETRIEVAL, RECORD):

        RECORD.data["file"] = "filepath"
        PDF_RETRIEVAL.review_manager.dataset.import_file(record=RECORD.data)

        return RECORD
