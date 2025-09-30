#! /usr/bin/env python
"""CustomName"""

from colrev.package_manager.package_base_classes import PDFPrepManPackageBaseClass

class CustomName(PDFPrepManPackageBaseClass):

    def __init__(self, *, pdf_prep_man_operation: 'colrev.ops.pdf_prep_man.PDFPrepMan', settings: 'dict', logger: 'Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def pdf_prep_man(self, records: 'dict') -> 'dict':
        """Run the pdf-prep-man operation."""
