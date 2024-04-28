#! /usr/bin/env python
"""Conditional prescreen"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import RecordState


# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.PrescreenInterface)
@dataclass
class ConditionalPrescreen(JsonSchemaMixin):
    """Conditional prescreen (currently: include all)"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = True

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.review_manager = prescreen_operation.review_manager

    def run_prescreen(
        self,
        records: dict,
        split: list,  # pylint: disable=unused-argument
    ) -> dict:
        """Prescreen records based on predefined conditions (rules)"""

        pad = 50
        for record in records.values():
            if record[Fields.STATUS] != RecordState.md_processed:
                continue
            self.review_manager.report_logger.info(
                f" {record[Fields.ID]}".ljust(pad, " ")
                + "Included in prescreen (automatically)"
            )
            # pylint: disable=colrev-direct-status-assign
            record.update(colrev_status=RecordState.rev_prescreen_included)

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(
            msg="Pre-screen (include_all)",
            manual_author=False,
        )
        return records
