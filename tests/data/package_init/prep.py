#! /usr/bin/env python
"""CustomName"""
import colrev.ops.prep
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import PrepPackageBaseClass

class CustomName(PrepPackageBaseClass):

    def __init__(self, *, prep_operation: 'colrev.ops.prep.Prep', settings: 'dict') -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def prepare(self, record: 'colrev.record.record_prep.PrepRecord') -> 'colrev.record.record.Record':
        """Run the prep operation."""
