#! /usr/bin/env python
"""CustomName"""
import logging
import typing

import colrev.ops.prescreen
from colrev.package_manager.package_base_classes import PrescreenPackageBaseClass

class CustomName(PrescreenPackageBaseClass):

    def __init__(self, *, prescreen_operation: 'colrev.ops.prescreen.Prescreen', settings: 'dict', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def run_prescreen(self, records: 'dict', split: 'list') -> 'dict':
        """Run the prescreen operation."""
