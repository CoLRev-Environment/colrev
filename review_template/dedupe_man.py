#! /usr/bin/env python
import logging
import os
import pprint

import pandas as pd

from review_template.review_manager import RecordState

logger = logging.getLogger("review_template")

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)


def get_combined_origin_list(record_a: dict, record_b: dict) -> str:

    o_record_a = record_a["origin"].split(";")
    o_record_b = record_b["origin"].split(";")

    combined_origin_list = set(o_record_a + o_record_b)

    return ";".join(combined_origin_list)


def remove_from_potential_duplicates_csv(ID1, ID2):
    with open("potential_duplicate_tuples.csv", "r+b") as fd:
        seekpos = fd.tell()
        line = fd.readline()
        while line:
            if ID1.encode("utf-8") in line and ID2.encode("utf-8") in line:
                remaining = fd.read()
                fd.seek(seekpos)
                seekpos = fd.tell()
                fd.flush()
                os.fsync(fd)
                fd.write(remaining)
                fd.truncate()
                fd.seek(seekpos)
            else:
                fd.seek(seekpos)
                fd.write(line)
                seekpos = fd.tell()
            line = fd.readline()
    return


def apply_manual_dedupe_decision(REVIEW_MANAGER, bib_db, dedupe_man_item):

    main_ID = dedupe_man_item["main_ID"]
    duplicate_ID = dedupe_man_item["duplicate_ID"]
    # TODO : get record by id
    main_record = [x for x in bib_db.entries if main_ID == x["ID"]][0]
    duplicate_record = [x for x in bib_db.entries if duplicate_ID == x["ID"]][0]

    if "no_duplicate" == dedupe_man_item["decision"]:
        logger.info(
            f"{main_ID}/{duplicate_ID}".ljust(40, " ") + "recorded: no duplicate"
        )
        # do not merge records
        remove_from_potential_duplicates_csv(main_ID, duplicate_ID)
        # if ID is in no other potential duplicate pairs, set status to md_processed
        with open("potential_duplicate_tuples.csv") as f:
            if main_ID not in f.read():
                main_record.update(status=RecordState.md_processed)
        with open("potential_duplicate_tuples.csv") as f:
            if duplicate_ID not in f.read():
                duplicate_record.update(status=RecordState.md_processed)

    if "duplicate" == dedupe_man_item["decision"]:
        logger.info(f"{main_ID}/{duplicate_ID}".ljust(40, " ") + "recorded: duplicate")
        # Note: update status and remove the other record
        combined_el_list = get_combined_origin_list(main_record, duplicate_record)
        # Delete the other record (record_a_ID or record_b_ID)
        main_record.update(origin=combined_el_list)

        main_record.update(status=RecordState.md_processed)
        bib_db.entries = [
            x for x in bib_db.entries if x["ID"] != duplicate_record["ID"]
        ]
        remove_from_potential_duplicates_csv(main_ID, duplicate_ID)

    potential_duplicate_tuples_empty = False
    with open("potential_duplicate_tuples.csv") as f:
        lines = f.readlines()
        if 1 == len(lines) and "max_similarity" in lines[0]:
            potential_duplicate_tuples_empty = True
    if potential_duplicate_tuples_empty:
        os.remove("potential_duplicate_tuples.csv")

    REVIEW_MANAGER.save_bib_file(bib_db)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.git.add(update=True)

    return bib_db


def get_data(REVIEW_MANAGER, bib_db):
    from review_template.review_manager import RecordState, Process, ProcessType

    REVIEW_MANAGER.notify(Process(ProcessType.dedupe_man))

    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = (
        len(
            [
                x
                for x in record_state_list
                if str(RecordState.md_needs_manual_deduplication) == x[1]
            ]
        )
        // 2
    )
    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)

    if not os.path.exists("potential_duplicate_tuples.csv"):
        logger.info("No potential duplicates found (potential_duplicate_tuples.csv)")
        items = []
    else:
        potential_duplicates = pd.read_csv("potential_duplicate_tuples.csv")
        items = potential_duplicates.to_dict("records")
        for item in items:
            record_a_ID = item["ID1"]
            record_b_ID = item["ID2"]

            if not all(
                rid in [x["ID"] for x in bib_db.entries]
                for rid in [record_a_ID, record_b_ID]
            ):
                # Note: record IDs may no longer be in records
                # due to prior merging operations
                item["decision"] = "ID_no_longer_in_records"
                continue

            a_propagated = REVIEW_MANAGER.propagated_ID(record_a_ID)
            b_propagated = REVIEW_MANAGER.propagated_ID(record_b_ID)

            if not a_propagated and not b_propagated:

                # Use the record['ID'] without appended letters if possible
                # Set a_propagated=True if record_a_ID should be kept
                if record_a_ID[-1:].isnumeric() and not record_b_ID[-1:].isnumeric():
                    a_propagated = True
                else:
                    b_propagated = True
                    # This arbitrarily uses record_b_ID
                    # if none of the IDs has a letter appended.

            if a_propagated and b_propagated:
                item["decision"] = "both_IDs_propagated"
                logger.error(f"Both IDs propagated: {record_a_ID}, {record_b_ID}")
                # return bib_db
                continue

            if a_propagated:
                item["main_ID"] = [
                    x["ID"] for x in bib_db.entries if record_a_ID == x["ID"]
                ][0]
                item["duplicate_ID"] = [
                    x["ID"] for x in bib_db.entries if record_b_ID == x["ID"]
                ][0]
            else:
                item["main_ID"] = [
                    x["ID"] for x in bib_db.entries if record_b_ID == x["ID"]
                ][0]
                item["duplicate_ID"] = [
                    x["ID"] for x in bib_db.entries if record_a_ID == x["ID"]
                ][0]
            del item["ID1"]
            del item["ID2"]

    dedupe_man_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
    logger.debug(pp.pformat(dedupe_man_data))

    return dedupe_man_data
