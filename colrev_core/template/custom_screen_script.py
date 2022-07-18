#! /usr/bin/env python
import random

import zope.interface

from colrev_core.process import ScreenEndpoint
from colrev_core.record import ScreenRecord


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

            SCREEN_RECORD = ScreenRecord(data=record)

            if random.random() < 0.5:
                if exclusion_criteria_available:
                    # record criteria
                    pass
                SCREEN_RECORD.screen(
                    REVIEW_MANAGER=SCREEN.REVIEW_MANAGER,
                    screen_inclusion=True,
                    exclusion_criteria="...",
                )

            else:
                if exclusion_criteria_available:
                    # record criteria
                    pass
                SCREEN_RECORD.screen(
                    REVIEW_MANAGER=SCREEN.REVIEW_MANAGER,
                    screen_inclusion=False,
                    exclusion_criteria="...",
                )

        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        SCREEN.REVIEW_MANAGER.create_commit(
            msg="Screen (random)", manual_author=False, script_call="colrev screen"
        )
        return records
