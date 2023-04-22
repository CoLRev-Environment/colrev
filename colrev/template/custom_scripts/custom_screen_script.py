#! /usr/bin/env python
"""Template for a custom Screen PackageEndpoint"""
from __future__ import annotations

import random

import zope.interface
from dacite import from_dict

import colrev.operation
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.screen.Screen

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.ScreenPackageEndpointInterface)
class CustomScreen:
    """Class for custom screen scripts"""

    def __init__(
        self,
        *,
        screen_operation: colrev.screen.Screen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.env.package_manager.DefaultSettings, data=settings
        )

    def run_screen(
        self, screen_operation: colrev.screen.Screen, records: dict, split: list
    ) -> dict:
        """Screen a record"""

        screen_data = screen_operation.get_data()
        screening_criteria = screen_operation.review_manager.settings.screen.criteria

        screening_criteria_available = bool(screening_criteria)

        for record_dict in screen_data["items"]:
            if len(split) > 0:
                if record_dict["ID"] not in split:
                    continue

            record = colrev.record.Record(data=record_dict)

            if random.random() < 0.5:  # nosec
                if screening_criteria_available:
                    # record criteria
                    pass
                screen_operation.screen(
                    record=record,
                    screen_inclusion=True,
                    screening_criteria="...",
                )

            else:
                if screening_criteria_available:
                    # record criteria
                    pass
                screen_operation.screen(
                    record=record,
                    screen_inclusion=False,
                    screening_criteria="...",
                )

        screen_operation.review_manager.dataset.save_records_dict(records=records)
        screen_operation.review_manager.dataset.add_record_changes()
        screen_operation.review_manager.create_commit(
            msg="Screen (random)", manual_author=False, script_call="colrev screen"
        )
        return records
