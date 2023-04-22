#! /usr/bin/env python
"""Template for a custom Prescreen PackageEndpoint"""
from __future__ import annotations

import random

import zope.interface
from dacite import from_dict

import colrev.operation
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prescreen

# pylint: disable=too-few-public-methods


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
class CustomPrescreen:
    """Class for custom prescreen scripts"""

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.env.package_manager.DefaultSettings, data=settings
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
                    record=colrev.record.Record(data=record), prescreen_inclusion=True
                )

            else:
                prescreen_operation.prescreen(
                    record=colrev.record.Record(data=record), prescreen_inclusion=False
                )

        prescreen_operation.review_manager.dataset.save_records_dict(records=records)
        prescreen_operation.review_manager.dataset.add_record_changes()
        prescreen_operation.review_manager.create_commit(
            msg="Pre-screen (random)",
            manual_author=False,
            script_call="colrev prescreen",
        )

        return records
