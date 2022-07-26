#! /usr/bin/env python
import zope.interface
from dacite import from_dict

from colrev_core.process import DataEndpoint
from colrev_core.process import DefaultSettings


@zope.interface.implementer(DataEndpoint)
class CustomData:
    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def get_default_setup(self):
        custom_endpoint_details = {
            "endpoint": "CustomDataFormat",
            "custom_data_format_version": "0.1",
            "config": {},
        }
        return custom_endpoint_details

    def update_data(self, DATA, records: dict, synthesized_record_status_matrix: dict):
        pass

    def update_record_status_matrix(
        self, DATA, synthesized_record_status_matrix, endpoint_identifier
    ):
        # Note : automatically set all to True / synthesized
        for syn_ID in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_ID][endpoint_identifier] = True
