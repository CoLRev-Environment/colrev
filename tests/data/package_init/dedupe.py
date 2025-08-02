#! /usr/bin/env python
"""CustomName"""
import logging
from typing import Optional

import colrev.ops.dedupe
from colrev.package_manager.package_base_classes import DedupePackageBaseClass

class CustomName(DedupePackageBaseClass):

    def __init__(self, *, dedupe_operation: 'colrev.ops.dedupe.Dedupe', settings: 'dict', logger: 'Optional[logging.Logger]' = None):
        """Initialize self.  See help(type(self)) for accurate signature."""

    def run_dedupe(self) -> 'None':
        """Run the dedupe operation."""
