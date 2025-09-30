#! /usr/bin/env python
"""CustomName"""
import logging
import typing

import colrev.ops.data
from colrev.package_manager.package_base_classes import ReviewTypePackageBaseClass

class CustomName(ReviewTypePackageBaseClass):

    def __init__(self, *, operation: 'colrev.process.operation.Operation', settings: 'dict', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def initialize(self, settings: 'colrev.settings.Settings') -> 'dict':
        """Initialize the review type"""
