#! /usr/bin/env python
import zope.interface
from dacite import from_dict

from colrev_core.process import DefaultSettings
from colrev_core.process import PDFRetrievalManualEndpoint


@zope.interface.implementer(PDFRetrievalManualEndpoint)
class CoLRevCLIPDFRetrievalManual:
    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def get_man_pdf(self, PDF_RETRIEVAL_MAN, records):

        from colrev.cli import pdf_get_man_cli

        records = pdf_get_man_cli(PDF_RETRIEVAL_MAN, records)

        return records
