#! /usr/bin/env python
import logging
import os
import pprint
from pathlib import Path

import git
import imagehash
from pdf2image import convert_from_path

from colrev_core.review_manager import RecordState

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")
pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def file_is_git_versioned(git_repo: git.Repo, filePath: Path) -> bool:
    pathdir = os.path.dirname(str(filePath))
    rsub = git_repo.head.commit.tree
    for path_element in pathdir.split(os.path.sep):
        try:
            rsub = rsub[path_element]
        except KeyError:
            return False
    return filePath in rsub


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
        conditions={"status": RecordState.pdf_needs_manual_preparation}
    )
    pdf_prep_man_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
    logger.debug(pp.pformat(pdf_prep_man_data))
    return pdf_prep_man_data


def set_data(REVIEW_MANAGER, record, PAD: int = 40) -> None:

    git_repo = REVIEW_MANAGER.get_repo()

    record.update(status=RecordState.pdf_prepared)
    if file_is_git_versioned(git_repo, record["file"]):
        git_repo.index.add([record["file"]])

    if "pdf_prep_hints" in record:
        del record["pdf_prep_hints"]

    record.update(
        pdf_hash=str(
            imagehash.average_hash(
                convert_from_path(record["file"], first_page=0, last_page=1)[0],
                hash_size=32,
            )
        )
    )

    REVIEW_MANAGER.update_record_by_ID(record)
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

    return


def pdfs_prepared_manually(REVIEW_MANAGER) -> bool:
    git_repo = REVIEW_MANAGER.get_repo()
    return git_repo.is_dirty()


def pdf_prep_man_stats(REVIEW_MANAGER) -> None:

    from colrev_core.review_manager import Process, ProcessType
    import pandas as pd

    REVIEW_MANAGER.notify(Process(ProcessType.explore))
    # TODO : this function mixes return values and saving to files.
    logger.info(f"Load {REVIEW_MANAGER.paths['MAIN_REFERENCES_RELATIVE']}")
    records = REVIEW_MANAGER.load_records()

    logger.info("Calculate statistics")
    stats: dict = {"ENTRYTYPE": {}}

    prep_man_hints = []
    crosstab = []
    for record in records:

        if RecordState.pdf_needs_manual_preparation != record["status"]:
            continue

        if record["ENTRYTYPE"] in stats["ENTRYTYPE"]:
            stats["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
            )
        else:
            stats["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

        if "pdf_prep_hints" in record:
            hints = record["pdf_prep_hints"].split(";")
            prep_man_hints.append(hints)

            for hint in hints:
                crosstab.append([record["journal"], hint])

    crosstab_df = pd.DataFrame(crosstab, columns=["journal", "hint"])

    if crosstab_df.empty:
        print("No records to prepare manually.")
    else:
        tabulated = pd.pivot_table(
            crosstab_df[["journal", "hint"]],
            index=["journal"],
            columns=["hint"],
            aggfunc=len,
            fill_value=0,
            margins=True,
        )
        # .sort_index(axis='columns')
        tabulated.sort_values(by=["All"], ascending=False, inplace=True)
        # Transpose because we tend to have more error categories than search files.
        tabulated = tabulated.transpose()
        print(tabulated)
        logger.info("Writing data to file: manual_preparation_statistics.csv")
        tabulated.to_csv("manual_pdf_preparation_statistics.csv")

    return
