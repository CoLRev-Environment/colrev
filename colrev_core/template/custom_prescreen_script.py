#! /usr/bin/env python
import random

import zope.interface

from colrev_core.prescreen import PrescreenEndpoint
from colrev_core.record import RecordState


@zope.interface.implementer(PrescreenEndpoint)
class CustomPrescreen:
    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:

        for record in records.values():
            if random.random() < 0.5:
                record.update(colrev_status=RecordState.rev_prescreen_included)
            else:
                record.update(colrev_status=RecordState.rev_prescreen_excluded)

        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        PRESCREEN.REVIEW_MANAGER.create_commit(
            msg="Pre-screen (random)", manual_author=False
        )
        return records
