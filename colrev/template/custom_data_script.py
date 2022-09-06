#! /usr/bin/env python
from __future__ import annotations

from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.process


if TYPE_CHECKING:
    import colrev.ops.data


@zope.interface.implementer(colrev.process.DataEndpoint)
class CustomData:
    def __init__(self, *, data_operation, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def get_default_setup(self):
        custom_endpoint_details = {
            "endpoint": "CustomDataFormat",
            "custom_data_format_version": "0.1",
            "config": {},
        }
        return custom_endpoint_details

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,
    ) -> None:
        pass

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        # Note : automatically set all to True / synthesized
        for syn_ID in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_ID][endpoint_identifier] = True
