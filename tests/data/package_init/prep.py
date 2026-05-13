#! /usr/bin/env python
"""CustomName"""
import logging
import typing

import colrev.ops.prep
from colrev.package_manager.package_base_classes import PrepPackageBaseClass

class CustomName(PrepPackageBaseClass):

    def __init__(self, *, prep_operation: 'colrev.ops.prep.Prep', settings: 'dict', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize the instance."""

    def prepare(self, record: 'colrev.record.record_prep.PrepRecord') -> 'colrev.record.record.Record':
        """Run the prep operation."""
