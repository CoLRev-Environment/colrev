#! /usr/bin/env python
"""Template for a custom Prescreen PackageEndpoint"""
from __future__ import annotations

import random

import zope.interface
from dacite import from_dict

import colrev.package_manager.interfaces
import colrev.package_manager.package_settings
import colrev.process.operation
import colrev.record.record


# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.package_manager.interfaces.PrescreenInterface)
class CustomPrescreen:
    """Class for custom prescreen scripts"""

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.package_manager.package_settings.DefaultSettings,
            data=settings,
        )

    def run_prescreen(
        self,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,  # pylint: disable=unused-argument
    ) -> dict:
        """Prescreen the record"""

        for record in records.values():
            if random.random() < 0.5:  # nosec
                prescreen_operation.prescreen(
                    record=colrev.record.record.Record(record), prescreen_inclusion=True
                )

            else:
                prescreen_operation.prescreen(
                    record=colrev.record.record.Record(record),
                    prescreen_inclusion=False,
                )

        prescreen_operation.review_manager.dataset.save_records_dict(records)
        prescreen_operation.review_manager.dataset.create_commit(
            msg="Pre-screen (random)",
            manual_author=False,
            script_call="colrev prescreen",
        )

        return records
