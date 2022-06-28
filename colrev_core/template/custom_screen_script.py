#! /usr/bin/env python
import random

import zope.interface

from colrev_core.record import RecordState
from colrev_core.screen import ScreenEndpoint


@zope.interface.implementer(ScreenEndpoint)
class CustomScreen:
    @classmethod
    def run_screen(cls, SCREEN, records: dict, split: list) -> dict:

        screen_data = SCREEN.get_data()
        exclusion_criteria_full = SCREEN.REVIEW_MANAGER.settings.screen.criteria

        exclusion_criteria = [c.name for c in exclusion_criteria_full]
        if exclusion_criteria:
            exclusion_criteria_available = True
        else:
            exclusion_criteria_available = False
            exclusion_criteria = ["NA"]

        for record in screen_data["items"]:
            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            if random.random() < 0.5:
                record.update(colrev_status=RecordState.rev_included)
                if exclusion_criteria_available:
                    # record criteria
                    pass
                SCREEN.set_data(record=record)
            else:
                record.update(colrev_status=RecordState.rev_excluded)
                if exclusion_criteria_available:
                    # record criteria
                    pass
                SCREEN.set_data(record=record)

        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        SCREEN.REVIEW_MANAGER.create_commit(msg="Screen (random)", manual_author=False)
        return records
