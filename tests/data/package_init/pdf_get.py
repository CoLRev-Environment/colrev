#! /usr/bin/env python
"""CustomName"""
import colrev.ops.pdf_get
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import PDFGetPackageBaseClass

class CustomName(PDFGetPackageBaseClass):

    def __init__(self, *, pdf_get_operation: 'colrev.ops.pdf_get.PDFGet', settings: 'dict') -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def get_pdf(self, record: 'colrev.record.record.Record') -> 'colrev.record.record.Record':
        """Run the pdf-get operation."""
