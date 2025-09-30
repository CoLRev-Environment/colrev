#! /usr/bin/env python
"""CustomName"""

from colrev.package_manager.package_base_classes import PrepManPackageBaseClass

class CustomName(PrepManPackageBaseClass):

    def __init__(self, *, prep_man_operation: 'colrev.ops.prep_man.PrepMan', settings: 'dict', logger: 'Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def prepare_manual(self, records: 'dict') -> 'dict':
        """Run the prep-man operation."""
