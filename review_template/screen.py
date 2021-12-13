#! /usr/bin/env python
import logging
import pprint

from bibtexparser.bibdatabase import BibDatabase

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

report_logger = logging.getLogger("review_template_report")
logger = logging.getLogger("review_template")
pp = pprint.PrettyPrinter(indent=4, width=140)


def get_excl_criteria(ec_string: str) -> list:
    return [ec.split("=")[0] for ec in ec_string.split(";") if ec != "NA"]


def get_exclusion_criteria_from_str(ec_string: str) -> list:
    if ec_string:
        excl_criteria = get_excl_criteria(ec_string)
    else:
        excl_criteria_str = input("Exclusion criteria (comma separated or NA)")
        excl_criteria = excl_criteria_str.split(",")
        if "" in excl_criteria:
            excl_criteria.remove("")
    if "NA" in excl_criteria:
        excl_criteria.remove("NA")

    return excl_criteria


def get_exclusion_criteria(bib_db: BibDatabase) -> list:
    ec_string = [x.get("excl_criteria") for x in bib_db.entries if "excl_criteria" in x]
    return get_exclusion_criteria_from_str(ec_string[0])


def get_data(REVIEW_MANAGER):
    from review_template.review_manager import RecordState
    from review_template.review_manager import Process, ProcessType

    REVIEW_MANAGER.notify(Process(ProcessType.screen))

    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [x for x in record_state_list if str(RecordState.pdf_prepared) == x[1]]
    )
    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)
    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": str(RecordState.pdf_prepared)}
    )
    screen_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
    logger.debug(pp.pformat(screen_data))
    return screen_data


def set_data(REVIEW_MANAGER, record: dict, PAD: int = 40) -> None:
    from review_template.review_manager import RecordState

    git_repo = REVIEW_MANAGER.get_repo()

    if RecordState.rev_included == record["status"]:
        report_logger.info(f" {record['ID']}".ljust(PAD, " ") + "Included in screen")
        REVIEW_MANAGER.update_record_by_ID(record)
    else:
        report_logger.info(f" {record['ID']}".ljust(PAD, " ") + "Excluded in screen")
        REVIEW_MANAGER.update_record_by_ID(record)

    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

    return
