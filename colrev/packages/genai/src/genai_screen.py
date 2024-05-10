#! /usr/bin/env python
"""Screen based on GenAI"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.settings
from colrev.constants import RecordState


@zope.interface.implementer(colrev.package_manager.interfaces.ScreenInterface)
@dataclass
class GenAIScreen(JsonSchemaMixin):
    """Screen documents using GenAI"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = False
    export_todos_only: bool = True

    def __init__(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,
        settings: dict,
    ) -> None:
        self.review_manager = screen_operation.review_manager
        self.screen_operation = screen_operation
        self.settings = self.settings_class.load_settings(data=settings)

        # TODO : load API-Key and initialize connection here

    def run_screen(self, records: dict, split: list) -> dict:
        """Screen records based on GenAI"""

        # TODO : add logic based on records and split here

        # screening_criteria = self.review_manager.settings.screen.criteria
        for record_dict in records.values():
            record = colrev.record.record.Record(record_dict)
            # record.data[Fields.FILE] should be available (maybe even TEI documents)
            record.set_status(RecordState.rev_excluded)
            record.set_status(RecordState.rev_included)
            # screening_criteria_field = "reason_1=in;reason_2=out" # reasons: see screening_criteria
            # record.data[Fields.SCREENING_CRITERIA] = screening_criteria_field

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(msg="Screen (GenAI)")

        return records
