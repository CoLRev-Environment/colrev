#! /usr/bin/env python
"""CustomName"""
import colrev.ops.pdf_prep_man
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import PDFPrepManPackageBaseClass

class CustomName(PDFPrepManPackageBaseClass):

    def __init__(self, *, pdf_prep_man_operation: 'colrev.ops.pdf_prep_man.PDFPrepMan', settings: 'dict') -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def pdf_prep_man(self, records: 'dict') -> 'dict':
        """Run the pdf-prep-man operation."""
