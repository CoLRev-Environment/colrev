#! /usr/bin/env python
import zope.interface

from colrev_core.process import PDFPreparationManualEndpoint


@zope.interface.implementer(PDFPreparationManualEndpoint)
class CoLRevCLIPDFManPrep:
    def prep_man_pdf(self, PDF_PREP_MAN, records):

        from colrev.cli import pdf_prep_man_cli

        records = pdf_prep_man_cli(PDF_PREP_MAN, records)

        return records
