#! /usr/bin/env python
"""CustomName"""
import logging
import typing

import colrev.search_file
from colrev.package_manager.package_base_classes import SearchSourcePackageBaseClass

class CustomName(SearchSourcePackageBaseClass):

    def __init__(self, *, search_file: 'colrev.search_file.ExtendedSearchFile', logger: 'typing.Optional[logging.Logger]' = None, verbose_mode: 'bool' = False) -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def load(self) -> 'dict':
        """Load records from the SearchSource."""

    def prep_link_md(self, prep_operation: 'colrev.ops.prep.Prep', record: 'colrev.record.record.Record', save_feed: 'bool' = True, timeout: 'int' = 10) -> 'colrev.record.record.Record':
        """Retrieve masterdata from the SearchSource."""

    def prepare(self, record: 'colrev.record.record_prep.PrepRecord') -> 'colrev.record.record.Record':
        """Run the custom source-prep operation."""

    def search(self, rerun: 'bool') -> 'None':
        """Run a search of the SearchSource."""
