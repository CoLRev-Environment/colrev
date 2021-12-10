#! /usr/bin/env python
import logging

from review_template.review_manager import RecordState


logger = logging.getLogger("review_template_report")


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


def set_data(REVIEW_MANAGER, record, PAD: int = 40) -> None:

    git_repo = REVIEW_MANAGER.get_repo()

    record.update(status=RecordState.pdf_prepared)
    if "GIT" == REVIEW_MANAGER.config["PDF_HANDLING"]:
        git_repo.index.add([record["file"]])

    REVIEW_MANAGER.update_record_by_ID(record)
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

    return


def pdfs_prepared_manually(REVIEW_MANAGER) -> bool:
    git_repo = REVIEW_MANAGER.get_repo()
    return git_repo.is_dirty()
