#! /usr/bin/env python
"""CustomName"""
import logging
import typing

import colrev.ops.screen
from colrev.package_manager.package_base_classes import ScreenPackageBaseClass

class CustomName(ScreenPackageBaseClass):

    def __init__(self, *, screen_operation: 'colrev.ops.screen.Screen', settings: 'dict', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def run_screen(self, records: 'dict', split: 'list') -> 'dict':
        """Run the screen operation."""
