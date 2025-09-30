#! /usr/bin/env python
"""CustomName"""
import logging
import typing

import colrev.ops.pdf_prep
from colrev.package_manager.package_base_classes import PDFPrepPackageBaseClass

class CustomName(PDFPrepPackageBaseClass):

    def __init__(self, *, pdf_prep_operation: 'colrev.ops.pdf_prep.PDFPrep', settings: 'dict', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def prep_pdf(self, record: 'colrev.record.record_pdf.PDFRecord', pad: 'int') -> 'colrev.record.record.Record':
        """Run the prep-pdf operation."""
