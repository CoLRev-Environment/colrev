#! /usr/bin/env python
import zope.interface
from dacite import from_dict

import colrev_core.process


@zope.interface.implementer(colrev_core.process.PDFPreparationManualEndpoint)
class CoLRevCLIPDFManPrep:
    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def prep_man_pdf(self, PDF_PREP_MAN, records):

        from colrev.cli import pdf_prep_man_cli

        pdf_prep_man_cli(PDF_PREP_MAN, records)

        return records
