#! /usr/bin/env python
"""Screen based on GenAI"""
from __future__ import annotations

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import RecordState

# pylint: disable=too-few-public-methods


class GenAIScreen(base_classes.ScreenPackageBaseClass):
    """Screen documents using GenAI"""

    ci_supported: bool = Field(default=False)
    export_todos_only: bool = True

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    def __init__(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,
        settings: dict,
    ) -> None:
        self.review_manager = screen_operation.review_manager
        self.screen_operation = screen_operation
        self.settings = self.settings_class(**settings)

    # pylint: disable=unused-argument
    def run_screen(self, records: dict, split: list) -> dict:
        """Screen records based on GenAI"""

        # screening_criteria = self.review_manager.settings.screen.criteria
        for record_dict in records.values():
            record = colrev.record.record.Record(record_dict)
            # record.data[Fields.FILE] should be available (maybe even TEI documents)
            record.set_status(RecordState.rev_excluded)
            record.set_status(RecordState.rev_included)
            # reasons: see screening_criteria
            # screening_criteria_field = "reason_1=in;reason_2=out"
            # record.data[Fields.SCREENING_CRITERIA] = screening_criteria_field

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(msg="Screen (GenAI)")

        return records
