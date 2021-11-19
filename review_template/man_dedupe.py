#! /usr/bin/env python
import csv
import difflib
import logging
import os

import ansiwrap
import git
import pandas as pd
from bibtexparser.bibdatabase import BibDatabase
from dictdiffer import diff

from review_template import repo_setup
from review_template import utils

removed_tuples = []

BATCH_SIZE = repo_setup.config["BATCH_SIZE"]


def get_combined_origin_list(record_a: dict, record_b: dict) -> str:

    o_record_a = record_a["origin"].split(";")
    o_record_b = record_b["origin"].split(";")

    combined_origin_list = set(o_record_a + o_record_b)

    return ";".join(combined_origin_list)


class colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    ORANGE = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def print_diff(change: dict, prefix_len: int) -> None:

    d = difflib.Differ()

    if change[0] == "change":
        if change[1] not in ["ID", "rev_status", "md_status", "pdf_status"]:
            letters = list(d.compare(change[2][0], change[2][1]))
            for i in range(len(letters)):
                if letters[i].startswith("  "):
                    letters[i] = letters[i][-1]
                elif letters[i].startswith("+ "):
                    letters[i] = f"{colors.RED}" + letters[i][-1] + f"{colors.END}"
                elif letters[i].startswith("- "):
                    letters[i] = f"{colors.GREEN}" + letters[i][-1] + f"{colors.END}"
            prefix = change[1] + ": "
            print(
                ansiwrap.fill(
                    "".join(letters),
                    initial_indent=prefix.ljust(prefix_len),
                    subsequent_indent=" " * prefix_len,
                )
            )
    elif change[0] == "add":
        prefix = change[1] + ": "
        print(
            ansiwrap.fill(
                f"{colors.RED}{change[2]}{colors.END}",
                initial_indent=prefix.ljust(prefix_len),
                subsequent_indent=" " * prefix_len,
            )
        )
    elif change[0] == "remove":
        prefix = change[1] + ": "
        print(
            ansiwrap.fill(
                f"{colors.GREEN}{change[2]}{colors.END}",
                initial_indent=prefix.ljust(prefix_len),
                subsequent_indent=" " * prefix_len,
            )
        )
    return


def merge_manual_dialogue(
    bib_db: BibDatabase, main_ID: str, duplicate_ID: str, stat: str
) -> BibDatabase:

    global quit_pressed
    global removed_tuples
    # Note: all changes must be made to the main_record (i.e., if we display
    # the main_record on the left side and if the user selects "1", this
    # means "no changes to the main record".)
    # We effectively have to consider only cases in which the user
    # wants to merge fields from the duplicate record into the main record

    main_record = [x for x in bib_db.entries if main_ID == x["ID"]][0]
    duplicate_record = [x for x in bib_db.entries if duplicate_ID == x["ID"]][0]

    # Escape sequence to clear terminal output for each new comparison
    os.system("cls" if os.name == "nt" else "clear")
    print(
        f"Merge {colors.GREEN}{main_record['ID']}{colors.END} < "
        + f"{colors.RED}{duplicate_record['ID']}{colors.END}?\n"
    )

    keys = set(list(main_record) + list(duplicate_record))

    differences = list(diff(main_record, duplicate_record))

    if len([x[2] for x in differences if "add" == x[0]]) > 0:
        added_fields = [y[0] for y in [x[2] for x in differences if "add" == x[0]][0]]
    else:
        added_fields = []
    if len([x[2] for x in differences if "remove" == x[0]]) > 0:
        removed_fields = [
            y[0] for y in [x[2] for x in differences if "remove" == x[0]][0]
        ]
    else:
        removed_fields = []
    prefix_len = len(max(keys, key=len) + ": ")
    for key in [
        "author",
        "title",
        "journal",
        "booktitle",
        "year",
        "volume",
        "number",
        "pages",
        "doi",
        "ENTRYTYPE",
    ]:
        if key in added_fields:
            change = [
                y
                for y in [x[2] for x in differences if "add" == x[0]][0]
                if key == y[0]
            ]
            print_diff(("add", *change[0]), prefix_len)
        elif key in removed_fields:
            change = [
                y
                for y in [x[2] for x in differences if "remove" == x[0]][0]
                if key == y[0]
            ]
            print_diff(("remove", *change[0]), prefix_len)
        elif key in [x[1] for x in differences]:
            change = [x for x in differences if x[1] == key]
            print_diff(change[0], prefix_len)
        elif key in keys:
            prefix = key + ": "
            print(
                ansiwrap.fill(
                    main_record[key],
                    initial_indent=prefix.ljust(prefix_len),
                    subsequent_indent=" " * prefix_len,
                )
            )

    response_string = "(" + stat + ") Merge records [y,n,d,q,?]? "
    response = input("\n" + response_string)
    while response not in ["y", "n", "d", "q"]:
        print(
            f"y - merge the {colors.RED}red record{colors.END} into the "
            + f"{colors.GREEN}green record{colors.END}"
        )
        print("n - keep both records (not duplicates)")
        print("d - detailed merge: decide for each field (to be implemented)")
        print("q - stop processing duplicate records")
        print("? - print help")
        response = input(response_string)

    if "y" == response:
        logging.info(f"{main_ID}/{duplicate_ID}".ljust(40, " ") + "recorded: duplicate")
        # Note: update md_status and remove the other record
        combined_el_list = get_combined_origin_list(main_record, duplicate_record)
        # Delete the other record (record_a_ID or record_b_ID)
        main_record.update(origin=combined_el_list)

        main_record.update(md_status="processed")
        bib_db.entries = [
            x for x in bib_db.entries if x["ID"] != duplicate_record["ID"]
        ]
        removed_tuples.append([main_ID, duplicate_ID])

    if "n" == response:
        logging.info(
            f"{main_ID}/{duplicate_ID}".ljust(40, " ") + "recorded: no duplicate"
        )
        # do not merge records/modify the bib_db
        removed_tuples.append([main_ID, duplicate_ID])
    # 'd' == response: TODO
    # Modification examples:
    # main_record.update(title='TEST')
    # main_record.update(title=duplicate_record['title])

    if "q" == response:
        quit_pressed = True

    return bib_db


def merge_manual(
    bib_db: BibDatabase, record_a_ID: str, record_b_ID: str, stat: str
) -> BibDatabase:
    global removed_tuples

    if not all(
        eid in [x["ID"] for x in bib_db.entries] for eid in [record_a_ID, record_b_ID]
    ):
        # Note: record IDs may no longer be in records
        # due to prior merging operations
        return bib_db

    a_propagated = utils.propagated_ID(record_a_ID)
    b_propagated = utils.propagated_ID(record_b_ID)

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
        logging.error(f"Both IDs propagated: {record_a_ID}, {record_b_ID}")
        return bib_db

    if a_propagated:
        main_ID = [x["ID"] for x in bib_db.entries if record_a_ID == x["ID"]][0]
        duplicate_ID = [x["ID"] for x in bib_db.entries if record_b_ID == x["ID"]][0]
    else:
        main_ID = [x["ID"] for x in bib_db.entries if record_b_ID == x["ID"]][0]
        duplicate_ID = [x["ID"] for x in bib_db.entries if record_a_ID == x["ID"]][0]

    bib_db = merge_manual_dialogue(bib_db, main_ID, duplicate_ID, stat)

    return bib_db


def main() -> None:
    saved_args = locals()
    global removed_tuples

    repo = git.Repo("")
    utils.require_clean_repo(repo)

    bib_db = utils.load_main_refs()

    if not os.path.exists("potential_duplicate_tuples.csv"):
        logging.info("No potential duplicates found (potential_duplicate_tuples.csv)")
        return

    potential_duplicate = pd.read_csv("potential_duplicate_tuples.csv")

    first_record_col = potential_duplicate.columns.get_loc("ID1")
    second_record_col = potential_duplicate.columns.get_loc("ID2")

    quit_pressed = False
    # Note: the potential_duplicate is ordered according to the last
    # column (similarity)
    stat = ""
    for i in range(0, potential_duplicate.shape[0]):
        record_a_ID = potential_duplicate.iloc[i, first_record_col]
        record_b_ID = potential_duplicate.iloc[i, second_record_col]

        stat = str(i + 1) + "/" + str(potential_duplicate.shape[0])
        bib_db = merge_manual(bib_db, record_a_ID, record_b_ID, stat)
        if quit_pressed:
            break

    for record_a_ID, record_b_ID in removed_tuples:
        potential_duplicate.drop(
            potential_duplicate[
                (potential_duplicate["ID1"] == record_a_ID)
                & (potential_duplicate["ID2"] == record_b_ID)
            ].index,
            inplace=True,
        )
        potential_duplicate.drop(
            potential_duplicate[
                (potential_duplicate["ID1"] == record_b_ID)
                & (potential_duplicate["ID2"] == record_a_ID)
            ].index,
            inplace=True,
        )

    not_completely_processed = (
        potential_duplicate["ID1"].tolist() + potential_duplicate["ID2"].tolist()
    )

    for record in bib_db.entries:
        if (
            record["ID"] not in not_completely_processed
            and "needs_manual_merging" == record["md_status"]
        ):
            record.update(md_status="processed")

    if potential_duplicate.shape[0] == 0:
        os.remove("potential_duplicate_tuples.csv")
    else:
        potential_duplicate.to_csv(
            "potential_duplicate_tuples.csv", index=False, quoting=csv.QUOTE_ALL
        )

    utils.save_bib_file(bib_db, repo_setup.paths["MAIN_REFERENCES"])
    repo.git.add(update=True)
    # deletion of 'potential_duplicate_tuples.csv' may added to git staging

    # If there are remaining duplicates, ask whether to create a commit
    if not stat.split("/")[0] == stat.split("/")[1]:
        if "y" != input("Create commit (y/n)?"):
            return
    utils.create_commit(
        repo, "Process duplicates manually", saved_args, manual_author=True
    )
    return
