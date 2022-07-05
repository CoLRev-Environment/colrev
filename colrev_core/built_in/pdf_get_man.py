#! /usr/bin/env python
import zope.interface

from colrev_core.process import PDFRetrievalManualEndpoint


@zope.interface.implementer(PDFRetrievalManualEndpoint)
class CoLRevCLIPDFRetrievalManual:
    def get_man_pdf(self, PDF_RETRIEVAL_MAN, records):

        from colrev.cli import pdf_get_man_cli

        records = pdf_get_man_cli(PDF_RETRIEVAL_MAN, records)

        return records
