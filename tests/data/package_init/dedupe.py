#! /usr/bin/env python
"""CustomName"""
import colrev.ops.dedupe
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import DedupePackageBaseClass

class CustomName(DedupePackageBaseClass):

    def __init__(self, *, dedupe_operation: 'colrev.ops.dedupe.Dedupe', settings: 'dict'):
        """Initialize self.  See help(type(self)) for accurate signature."""

    def run_dedupe(self) -> 'None':
        """Run the dedupe operation."""
