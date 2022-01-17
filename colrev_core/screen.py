#! /usr/bin/env python
import logging
import pprint
import typing

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")
pp = pprint.PrettyPrinter(indent=4, width=140)


def include_all_in_screen(REVIEW_MANAGER) -> None:
    from colrev_core.review_manager import Process, ProcessType, RecordState

    REVIEW_MANAGER.notify(Process(ProcessType.screen))
    records = REVIEW_MANAGER.load_records()

    excl_criteria = get_exclusion_criteria(records)

    saved_args = locals()
    saved_args["include_all"] = ""
    PAD = 50  # TODO
    for record in records:
        if record["status"] != RecordState.pdf_prepared:
            continue
        report_logger.info(
            f' {record["ID"]}'.ljust(PAD, " ") + "Included in screen (automatically)"
        )
        record.update(excl_criteria=";".join([e + "=no" for e in excl_criteria]))
        record.update(status=RecordState.rev_included)

    REVIEW_MANAGER.save_records(records)
    REVIEW_MANAGER.add_record_changes()
    REVIEW_MANAGER.create_commit(
        "Screen (include_all)", manual_author=False, saved_args=saved_args
    )

    return


def get_excl_criteria(ec_string: str) -> list:
    return [ec.split("=")[0] for ec in ec_string.split(";") if ec != "NA"]


def get_exclusion_criteria_from_str(ec_string: str) -> list:
    if ec_string != "":
        excl_criteria = get_excl_criteria(ec_string)
    else:
        excl_criteria_str = input("Exclusion criteria (comma separated or NA)")
        excl_criteria = excl_criteria_str.split(",")
        if "" in excl_criteria:
            excl_criteria.remove("")
    if "NA" in excl_criteria:
        excl_criteria.remove("NA")

    return excl_criteria


def get_exclusion_criteria(records: typing.List[dict]) -> list:
    ec_list = [x.get("excl_criteria") for x in records if "excl_criteria" in x]
    if 0 == len(ec_list):
        ec_string = ""
    else:
        ec_string = ec_list.pop()
    return get_exclusion_criteria_from_str(ec_string)


def get_data(REVIEW_MANAGER) -> dict:
    from colrev_core.review_manager import RecordState
    from colrev_core.review_manager import Process, ProcessType

    REVIEW_MANAGER.notify(Process(ProcessType.screen))

    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [x for x in record_state_list if str(RecordState.pdf_prepared) == x[1]]
    )
    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)
    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": RecordState.pdf_prepared}
    )
    screen_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
    logger.debug(pp.pformat(screen_data))
    return screen_data


def set_data(REVIEW_MANAGER, record: dict, PAD: int = 40) -> None:
    from colrev_core.review_manager import RecordState

    if RecordState.rev_included == record["status"]:
        report_logger.info(f" {record['ID']}".ljust(PAD, " ") + "Included in screen")
        REVIEW_MANAGER.update_record_by_ID(record)
    else:
        report_logger.info(f" {record['ID']}".ljust(PAD, " ") + "Excluded in screen")
        REVIEW_MANAGER.update_record_by_ID(record)

    REVIEW_MANAGER.add_record_changes()

    return
