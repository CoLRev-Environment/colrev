#! /usr/bin/env python
"""CustomName"""
import logging

import colrev.ops.data
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import ReviewTypePackageBaseClass

class CustomName(ReviewTypePackageBaseClass):

    def __init__(self, *, operation: 'colrev.process.operation.Operation', settings: 'dict', logger: 'logging.Logger' = logging.getLogger(__name__)) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def initialize(self, settings: 'colrev.settings.Settings') -> 'dict':
        """Initialize the review type"""
