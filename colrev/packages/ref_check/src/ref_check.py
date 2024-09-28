#! /usr/bin/env python
"""DataInterface: RefCheck"""
from zope.interface import implementer

import colrev.ops.data
import colrev.package_manager.package_settings
from colrev.package_manager.interfaces import DataInterface

# pylint: disable=unused-argument


@implementer(DataInterface)
class RefCheck:
    """RefCheck Class"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,
        settings: dict,
    ) -> None:
        self.data_operation = data_operation
        self.review_manager = data_operation.review_manager

    def update_data(
        self,
        records: dict,
        synthesized_record_status_matrix: dict,
        silent_mode: bool,
    ) -> None:
        """
        Update the data by running the data operation. This includes data extraction,
        analysis, and synthesis.

        Parameters:
        records (dict): The records to be updated.
        synthesized_record_status_matrix (dict): The status matrix for the synthesized records.
        silent_mode (bool): Whether the operation is run in silent mode
        (for checks of review_manager/status).
        """

    def update_record_status_matrix(
        self,
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record status matrix,
        i.e., indicate whether the record is rev_synthesized for the given endpoint_identifier
        """

        records = self.review_manager.dataset.load_records_dict()

        for syn_id in synthesized_record_status_matrix:
            record_dict = records[syn_id]
            record = colrev.record.record.Record(record_dict)
            if record.has_quality_defects():
                synthesized_record_status_matrix[syn_id][endpoint_identifier] = False
            else:
                synthesized_record_status_matrix[syn_id][endpoint_identifier] = True

    def get_advice(
        self,
    ) -> dict:
        """Get advice on how to operate the data package endpoint"""

        advice = {
            "msg": "Data operation [ref_check endpoint]: "
            + "\n    Prepare record metadata (or mark as IGNORE:...)",
            "detailed_msg": "... with a link to the docs etc.",
        }
        return advice
