#! /usr/bin/env python
"""CustomName"""
import colrev.ops.pdf_get_man
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import PDFGetManPackageBaseClass

class CustomName(PDFGetManPackageBaseClass):

    def __init__(self, *, pdf_get_man_operation: 'colrev.ops.pdf_get_man.PDFGetMan', settings: 'dict') -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def pdf_get_man(self, records: 'dict') -> 'dict':
        """Run the pdf-get-man operation."""
