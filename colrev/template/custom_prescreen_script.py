#! /usr/bin/env python
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.operation
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prescreen


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
class CustomPrescreen:
    def __init__(
        self, *, prescreen_operation: colrev.ops.prescreen.Prescreen, settings: dict
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.env.package_manager.DefaultSettings, data=settings
        )

    def run_prescreen(
        slef,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,
    ) -> dict:

        for record in records.values():
            if random.random() < 0.5:
                record.update(
                    colrev_status=colrev.record.RecordState.rev_prescreen_included
                )
            else:
                record.update(
                    colrev_status=colrev.record.RecordState.rev_prescreen_excluded
                )

        prescreen_operation.review_manager.dataset.save_records_dict(records=records)
        prescreen_operation.review_manager.dataset.add_record_changes()
        prescreen_operation.review_manager.create_commit(
            msg="Pre-screen (random)",
            manual_author=False,
            script_call="colrev prescreen",
        )

        # Alternatively (does not change the records argument   )
        # presscreen_data = prescreen_operation.get_data()
        # for record in prescreen_data["items"]:
        #   prescreen_record = PrescreenRecord(data=record)
        #   prescreen_record.prescreen(review_manager=prescreen_operation.review_manager,
        #                               prescreen_inclusion=True/False)

        return records
