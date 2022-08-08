#! /usr/bin/env python
import random

import zope.interface
from dacite import from_dict

import colrev_core.process
import colrev_core.record


@zope.interface.implementer(colrev_core.process.ScreenEndpoint)
class CustomScreen:
    def __init__(self, *, SCREEN, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def run_screen(self, SCREEN, records: dict, split: list) -> dict:

        screen_data = SCREEN.get_data()
        screening_criteria = SCREEN.REVIEW_MANAGER.settings.screen.criteria

        if screening_criteria:
            screening_criteria_available = True
        else:
            screening_criteria_available = False
            screening_criteria = ["NA"]

        for record in screen_data["items"]:
            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            SCREEN_RECORD = colrev_core.record.ScreenRecord(data=record)

            if random.random() < 0.5:
                if screening_criteria_available:
                    # record criteria
                    pass
                SCREEN_RECORD.screen(
                    REVIEW_MANAGER=SCREEN.REVIEW_MANAGER,
                    screen_inclusion=True,
                    screening_criteria="...",
                )

            else:
                if screening_criteria_available:
                    # record criteria
                    pass
                SCREEN_RECORD.screen(
                    REVIEW_MANAGER=SCREEN.REVIEW_MANAGER,
                    screen_inclusion=False,
                    screening_criteria="...",
                )

        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        SCREEN.REVIEW_MANAGER.create_commit(
            msg="Screen (random)", manual_author=False, script_call="colrev screen"
        )
        return records
