#! /usr/bin/env python
import logging

from review_template.review_manager import RecordState


logger = logging.getLogger("review_template")


def get_data(REVIEW_MANAGER):
    from review_template.review_manager import Process, ProcessType

    REVIEW_MANAGER.notify(Process(ProcessType.pdf_prep_man))

    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [
            x
            for x in record_state_list
            if str(RecordState.pdf_needs_manual_preparation) == x[1]
        ]
    )
    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 40)
    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": str(RecordState.pdf_needs_manual_preparation)}
    )
    return {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
