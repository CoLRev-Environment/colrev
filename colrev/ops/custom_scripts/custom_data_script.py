#! /usr/bin/env python
"""Template for a custom data PackageEndpoint"""
from __future__ import annotations

import zope.interface
from dacite import from_dict

import colrev.package_manager.interfaces
import colrev.package_manager.package_settings
import colrev.process.operation


@zope.interface.implementer(colrev.package_manager.interfaces.DataInterface)
class CustomData:
    """Class for custom data scripts"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def add_endpoint(cls, operation: colrev.ops.data.Data, params: str) -> None:
        """Add as an endpoint"""

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        records: dict,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
    ) -> None:
        """Update the data"""

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status matrix"""

        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_id][endpoint_identifier] = True
