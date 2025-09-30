#! /usr/bin/env python
"""CustomName"""
import logging
import typing

import colrev.ops.pdf_get_man
from colrev.package_manager.package_base_classes import PDFGetManPackageBaseClass

class CustomName(PDFGetManPackageBaseClass):

    def __init__(self, *, pdf_get_man_operation: 'colrev.ops.pdf_get_man.PDFGetMan', settings: 'dict', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def pdf_get_man(self, records: 'dict') -> 'dict':
        """Run the pdf-get-man operation."""
