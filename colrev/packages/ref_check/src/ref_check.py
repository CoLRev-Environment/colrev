#! /usr/bin/env python
"""DataInterface: RefCheck"""
from zope.interface import implementer

from colrev.package_manager.interfaces import DataInterface


@implementer(DataInterface)
class RefCheck:

    settings_class = ""  # TODO

    def __init__(self) -> None:
        pass

    def update_data(self, records, synthesized_record_status_matrix, silent_mode):
        """
        Update the data by running the data operation. This includes data extraction,
        analysis, and synthesis.

        Parameters:
        records (dict): The records to be updated.
        synthesized_record_status_matrix (dict): The status matrix for the synthesized records.
        silent_mode (bool): Whether the operation is run in silent mode
        (for checks of review_manager/status).
        """
        # TODO

    def update_record_status_matrix(
        self, synthesized_record_status_matrix, endpoint_identifier
    ):
        """Update the record status matrix,
        i.e., indicate whether the record is rev_synthesized for the given endpoint_identifier
        """
        # TODO

    def get_advice(
        self,
    ):
        """Get advice on how to operate the data package endpoint"""
        # TODO
