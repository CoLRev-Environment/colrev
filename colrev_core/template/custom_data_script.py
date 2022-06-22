#! /usr/bin/env python
import zope.interface

from colrev_core.data import DataEndpoint


@zope.interface.implementer(DataEndpoint)
class CustomData:
    def get_default_setup(self):
        custom_endpoint_details = {
            "endpoint": "CustomDataFormat",
            "custom_data_format_version": "0.1",
            "config": {},
        }
        return custom_endpoint_details

    def update_data(
        self, REVIEW_MANAGER, records: dict, synthesized_record_status_matrix: dict
    ):
        pass

    def update_record_status_matrix(
        self, REVIEW_MANAGER, synthesized_record_status_matrix, endpoint_identifier
    ):
        # Note : automatically set all to True / synthesized
        for syn_ID in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_ID][endpoint_identifier] = True
