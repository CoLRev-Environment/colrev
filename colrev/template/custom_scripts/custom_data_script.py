#! /usr/bin/env python
"""Template for a custom data PackageEndpoint"""
from __future__ import annotations

import zope.interface
from dacite import from_dict

import colrev.operation


if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
class CustomData:
    """Class for custom data scripts"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def get_default_setup(self) -> dict:
        """Get the default setup for the custom data script"""

        custom_endpoint_details = {
            "endpoint": "CustomDataFormat",
            "custom_data_format_version": "0.1",
            "config": {},
        }
        return custom_endpoint_details

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
