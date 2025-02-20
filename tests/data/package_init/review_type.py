#! /usr/bin/env python
"""CustomName"""
import colrev.ops.data
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import ReviewTypePackageBaseClass

class CustomName(ReviewTypePackageBaseClass):

    def __init__(self, *, operation: 'colrev.process.operation.Operation', settings: 'dict') -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def initialize(self, settings: 'colrev.settings.Settings') -> 'dict':
        """Initialize the review type"""
