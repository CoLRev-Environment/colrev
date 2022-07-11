#! /usr/bin/env python
import zope.interface
from dacite import from_dict

from colrev_core.process import DefaultSettings
from colrev_core.process import PDFPreparationManualEndpoint


@zope.interface.implementer(PDFPreparationManualEndpoint)
class CoLRevCLIPDFManPrep:
    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def prep_man_pdf(self, PDF_PREP_MAN, records):

        from colrev.cli import pdf_prep_man_cli

        records = pdf_prep_man_cli(PDF_PREP_MAN, records)

        return records
