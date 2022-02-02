#! /usr/bin/env python
import logging
import os
import pprint
from pathlib import Path

import bibtexparser
import git
import imagehash
import pandas as pd
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
            prep_man_hints.append([hint.lstrip() for hint in hints])

            for hint in hints:
                crosstab.append([record["journal"], hint.lstrip()])

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


def extract_needs_pdf_prep_man(REVIEW_MANAGER) -> None:

    from colrev_core.review_manager import Process, ProcessType
    from bibtexparser.bibdatabase import BibDatabase

    prep_bib_path = REVIEW_MANAGER.paths["REPO_DIR"] / Path("prep-references.bib")
    prep_csv_path = REVIEW_MANAGER.paths["REPO_DIR"] / Path("prep-references.csv")

    if prep_csv_path.is_file():
        print(f"Please rename file to avoid overwriting changes ({prep_csv_path})")
        return

    if prep_bib_path.is_file():
        print(f"Please rename file to avoid overwriting changes ({prep_bib_path})")
        return

    REVIEW_MANAGER.notify(Process(ProcessType.explore))
    logger.info(f"Load {REVIEW_MANAGER.paths['MAIN_REFERENCES_RELATIVE']}")
    records = REVIEW_MANAGER.load_records()

    records = [
        record
        for record in records
        if RecordState.pdf_needs_manual_preparation == record["status"]
    ]

    # Casting to string (in particular the RecordState Enum)
    records = [{k: str(v) for k, v in r.items()} for r in records]

    bib_db = BibDatabase()
    bib_db.entries = records
    bibtex_str = bibtexparser.dumps(bib_db)
    with open(prep_bib_path, "w") as out:
        out.write(bibtex_str)

    bib_db_df = pd.DataFrame.from_records(records)

    col_names = [
        "ID",
        "origin",
        "author",
        "title",
        "year",
        "journal",
        # "booktitle",
        "volume",
        "number",
        "pages",
        "doi",
    ]
    for col_name in col_names:
        if col_name not in bib_db_df:
            bib_db_df[col_name] = "NA"
    bib_db_df = bib_db_df[col_names]

    bib_db_df.to_csv(prep_csv_path, index=False)
    logger.info(f"Created {prep_csv_path.name}")

    return


def apply_pdf_prep_man(REVIEW_MANAGER) -> None:
    from colrev_core.review_manager import Process, ProcessType

    REVIEW_MANAGER.notify(Process(ProcessType.prep_man))

    if Path("prep-references.csv").is_file():
        logger.info("Load prep-references.csv")
        bib_db_df = pd.read_csv("prep-references.csv")
        bib_db_changed = bib_db_df.to_dict("records")
    if Path("prep-references.bib").is_file():
        logger.info("Load prep-references.bib")

        from bibtexparser.bparser import BibTexParser
        from bibtexparser.customization import convert_to_unicode

        with open("prep-references.bib") as target_db:
            bib_db = BibTexParser(
                customization=convert_to_unicode,
                ignore_nonstandard_types=False,
                common_strings=True,
            ).parse_file(target_db, partial=True)

            bib_db_changed = bib_db.entries

    records = REVIEW_MANAGER.load_records()
    for record in records:
        # IDs may change - matching based on origins
        changed_record_l = [
            x for x in bib_db_changed if x["origin"] == record["origin"]
        ]
        if len(changed_record_l) == 1:
            changed_record = changed_record_l.pop()
            for k, v in changed_record.items():
                # if record['ID'] == 'Alter2014':
                #     print(k, v)
                if str(v) == "nan":
                    if k in record:
                        del record[k]
                    continue
                record[k] = v
                if v == "":
                    del record[k]

    REVIEW_MANAGER.save_records(records)
    REVIEW_MANAGER.format_references()
    REVIEW_MANAGER.check_repo()
    return
