#! /usr/bin/env python
import zope.interface
from dacite import from_dict

import colrev_core.process


@zope.interface.implementer(colrev_core.process.PDFRetrievalManualEndpoint)
class CoLRevCLIPDFRetrievalManual:
    def __init__(self, *, PDF_RETRIEVAL_MAN, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def get_man_pdf(self, PDF_RETRIEVAL_MAN, records):

        from colrev.cli import pdf_get_man_cli

        pdf_get_man_cli(PDF_RETRIEVAL_MAN)

        return records
