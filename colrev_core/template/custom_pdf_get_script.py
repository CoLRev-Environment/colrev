#! /usr/bin/env python
import zope.interface
from dacite import from_dict

import colrev_core.process


@zope.interface.implementer(colrev_core.process.PDFRetrievalEndpoint)
class CustomPDFRetrieval:
    def __init__(self, *, PDF_GET, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def get_pdf(self, PDF_RETRIEVAL, RECORD):

        RECORD.data["file"] = "filepath"
        PDF_RETRIEVAL.REVIEW_MANAGER.REVIEW_DATASET.import_file(record=RECORD.data)

        return RECORD
