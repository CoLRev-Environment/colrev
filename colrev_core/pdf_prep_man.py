#! /usr/bin/env python
import logging
import pprint

from colrev_core.review_manager import RecordState


report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")
pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def get_data(REVIEW_MANAGER) -> dict:
    from colrev_core.review_manager import Process, ProcessType

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
    pdf_prep_man_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
    logger.debug(pp.pformat(pdf_prep_man_data))
    return pdf_prep_man_data


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
