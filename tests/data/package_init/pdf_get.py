#! /usr/bin/env python
"""CustomName"""
import logging
import typing

import colrev.ops.pdf_get
from colrev.package_manager.package_base_classes import PDFGetPackageBaseClass

class CustomName(PDFGetPackageBaseClass):

    def __init__(self, *, pdf_get_operation: 'colrev.ops.pdf_get.PDFGet', settings: 'dict', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def get_pdf(self, record: 'colrev.record.record.Record') -> 'colrev.record.record.Record':
        """Run the pdf-get operation."""
