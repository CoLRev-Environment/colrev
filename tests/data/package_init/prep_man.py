#! /usr/bin/env python
"""CustomName"""
import colrev.ops.prep_man
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import PrepManPackageBaseClass

class CustomName(PrepManPackageBaseClass):

    def __init__(self, *, prep_man_operation: 'colrev.ops.prep_man.PrepMan', settings: 'dict') -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def prepare_manual(self, records: 'dict') -> 'dict':
        """Run the prep-man operation."""
