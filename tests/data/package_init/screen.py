#! /usr/bin/env python
"""CustomName"""
import logging

import colrev.ops.screen
from colrev.package_manager.package_base_classes import ScreenPackageBaseClass


class CustomName(ScreenPackageBaseClass):

    def __init__(self, *, screen_operation: 'colrev.ops.screen.Screen', settings: 'dict', logger: 'logging.Logger | None' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize the instance."""

    def run_screen(self, records: 'dict', split: 'list') -> 'dict':
        """Run the screen operation."""
