#! /usr/bin/env python
"""CustomName"""
import colrev.ops.data
import colrev.package_manager.package_settings
from colrev.package_manager.package_base_classes import DataPackageBaseClass

class CustomName(DataPackageBaseClass):

    def __init__(self, *, data_operation: 'colrev.ops.data.Data', settings: 'dict') -> 'None':
        """Initialize self.  See help(type(self)) for accurate signature."""

    def get_advice(self) -> 'dict':
        """Get advice on how to operate the data package endpoint."""

    def update_data(self, records: 'dict', synthesized_record_status_matrix: 'dict', silent_mode: 'bool') -> 'None':
        """Update the data by running the data operation."""

    def update_record_status_matrix(self, synthesized_record_status_matrix: 'dict', endpoint_identifier: 'str') -> 'None':
        """Update the record status matrix."""
