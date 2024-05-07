#! /usr/bin/env python
"""Prescreen based on ChatGPT"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import RecordState


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.PrescreenInterface)
@dataclass
class ChatGPTPrescreen(JsonSchemaMixin):
    """ChatGPT-based prescreen"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = False
    export_todos_only: bool = True

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        settings: dict,
    ) -> None:
        self.review_manager = prescreen_operation.review_manager
        self.settings = self.settings_class.load_settings(data=settings)

        # TODO : load API-Key and initialize connection here

    def run_prescreen(
        self,
        records: dict,
        split: list,
    ) -> dict:
        """Prescreen records based on ChatGPT"""

        # TODO : add logic based on records and split here

        for record_dict in records.values():
            record = colrev.record.record.Record(record_dict)
            record.set_status(RecordState.rev_prescreen_included)
            # record.set_status(RecordState.rev_prescreen_excluded)

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(msg="Pre-screen (ChatGPT)")

        return records
