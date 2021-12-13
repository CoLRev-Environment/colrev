#! /usr/bin/env python
import itertools
import json
import logging
import re
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml
from bibtexparser.bibdatabase import BibDatabase
from yaml import safe_load

from review_template import review_manager
from review_template.review_manager import RecordState

report_logger = logging.getLogger("review_template_report")
logger = logging.getLogger("review_template")

PAD = 0


def get_records_for_synthesis(bib_db: BibDatabase) -> list:
    return [
        x["ID"]
        for x in bib_db.entries
        if x["status"] in [RecordState.rev_included, RecordState.rev_synthesized]
    ]


def get_data_page_missing(PAPER: Path, record_id_list: list) -> list:
    available = []
    with open(PAPER) as f:
        line = f.read()
        for record in record_id_list:
            if record in line:
                available.append(record)

    return list(set(record_id_list) - set(available))


def get_to_synthesize_in_manuscript(PAPER: Path, records_for_synthesis: list) -> list:
    in_manuscript_to_synthesize = []
    with open(PAPER) as f:
        for line in f:
            if "<!-- NEW_RECORD_SOURCE -->" in line:
                while line != "":
                    line = f.readline()
                    if re.search(r"- @.*", line):
                        ID = re.findall(r"- @(.*)$", line)
                        in_manuscript_to_synthesize.append(ID[0])
                        if line == "\n":
                            break

    in_manuscript_to_synthesize = [
        x for x in in_manuscript_to_synthesize if x in records_for_synthesis
    ]
    return in_manuscript_to_synthesize


def get_synthesized_ids(bib_db: BibDatabase, PAPER: Path) -> list:

    records_for_synthesis = get_records_for_synthesis(bib_db)

    in_manuscript_to_synthesize = get_to_synthesize_in_manuscript(
        PAPER, records_for_synthesis
    )
    # Assuming that all records have been added to the PAPER before
    synthesized = [
        x for x in records_for_synthesis if x not in in_manuscript_to_synthesize
    ]

    return synthesized


def get_data_extracted(DATA: Path, records_for_data_extraction: list) -> list:
    data_extracted = []
    with open(DATA) as f:
        data_df = pd.json_normalize(safe_load(f))

        for record in records_for_data_extraction:
            drec = data_df.loc[data_df["ID"] == record]
            if 1 == drec.shape[0]:
                if "TODO" not in drec.iloc[0].tolist():
                    data_extracted.append(drec.loc[0, "ID"])

    data_extracted = [x for x in data_extracted if x in records_for_data_extraction]
    return data_extracted


def get_structured_data_extracted(bib_db: BibDatabase, DATA: Path) -> list:

    if not DATA.is_dir():
        return []

    records_for_data_extraction = [
        x["ID"]
        for x in bib_db.entries
        if x["status"] in [RecordState.rev_included, RecordState.rev_synthesized]
    ]

    data_extracted = get_data_extracted(DATA, records_for_data_extraction)

    data_extracted = [x for x in data_extracted if x in records_for_data_extraction]

    return data_extracted


def add_missing_records_to_manuscript(PAPER: Path, missing_records: list) -> None:
    temp = tempfile.NamedTemporaryFile()
    PAPER.rename(temp.name)
    with open(temp.name) as reader, open(PAPER, "w") as writer:
        appended, completed = False, False
        line = reader.readline()
        while line != "":
            if "<!-- NEW_RECORD_SOURCE -->" in line:
                if "_Records to synthesize" not in line:
                    line = "_Records to synthesize_:" + line + "\n"
                    writer.write(line)
                else:
                    writer.write(line)
                    writer.write("\n")

                for missing_record in missing_records:
                    writer.write("- @" + missing_record + "\n")
                    report_logger.info(
                        f" {missing_record}".ljust(PAD, " ") + f" added to {PAPER.name}"
                    )

                    logger.info(
                        f" {missing_record}".ljust(PAD, " ") + f" added to {PAPER.name}"
                    )

                # skip empty lines between to connect lists
                line = reader.readline()
                if "\n" != line:
                    writer.write(line)

                appended = True

            elif appended and not completed:
                if "- @" == line[:3]:
                    writer.write(line)
                else:
                    if "\n" != line:
                        writer.write("\n")
                    writer.write(line)
                    completed = True
            else:
                writer.write(line)
            line = reader.readline()

        if not appended:
            msg = (
                "Marker <!-- NEW_RECORD_SOURCE --> not found in "
                + f"{PAPER.name}. Adding records at the end of "
                + "the document."
            )
            report_logger.warning(msg)
            logger.warning(msg)

            if line != "\n":
                writer.write("\n")
            marker = "<!-- NEW_RECORD_SOURCE -->_Records to synthesize_:\n\n"
            writer.write(marker)
            for missing_record in missing_records:
                writer.write("- @" + missing_record + "\n")
                report_logger.info(f" {missing_record}".ljust(PAD, " ") + " added")
                logger.info(f" {missing_record}".ljust(PAD, " ") + " added")

    return


def authorship_heuristic(REVIEW_MANAGER) -> str:
    git_repo = REVIEW_MANAGER.get_repo()
    commits_list = list(git_repo.iter_commits())
    commits_authors = []
    for commit in commits_list:
        committer = git_repo.git.show("-s", "--format=%cn", commit.hexsha)
        if "GitHub" == committer:
            continue
        commits_authors.append(committer)
        # author = repo.git.show("-s", "--format=%an", commit.hexsha)
        # mail = repo.git.show("-s", "--format=%ae", commit.hexsha)
    author = ", ".join(dict(Counter(commits_authors)))
    return author


def update_manuscript(
    REVIEW_MANAGER, bib_db: BibDatabase, included: list
) -> BibDatabase:

    PAPER = REVIEW_MANAGER.paths["PAPER"]
    PAPER_RELATIVE = REVIEW_MANAGER.paths["PAPER_RELATIVE"]

    if not PAPER.is_file():
        missing_records = included

        report_logger.info("Creating manuscript")
        logger.info("Creating manuscript")

        title = "Manuscript template"
        readme_file = REVIEW_MANAGER.paths["README"]
        if readme_file.is_file():
            with open(readme_file) as f:
                title = f.readline()
                title = title.replace("# ", "").replace("\n", "")

        author = authorship_heuristic(REVIEW_MANAGER)

        review_manager.retrieve_package_file(
            "template/" + str(PAPER_RELATIVE), str(PAPER)
        )
        review_manager.inplace_change(PAPER, "{{project_title}}", title)
        review_manager.inplace_change(PAPER, "{{author}}", author)
        logger.info(f"Please update title and authors in {PAPER.name}")

    report_logger.info("Updating manuscript")
    logger.info("Updating manuscript")
    missing_records = get_data_page_missing(PAPER, included)
    missing_records = sorted(missing_records)
    logger.debug(f"missing_records: {missing_records}")

    if 0 == len(missing_records):
        report_logger.info(f"All records included in {PAPER.name}")
        logger.info(f"All records included in {PAPER.name}")
    else:
        add_missing_records_to_manuscript(PAPER, missing_records)
        nr_records_added = len(missing_records)
        report_logger.info(f"{nr_records_added} records added to {PAPER.name}")
        logger.info(f"{nr_records_added} records added to {PAPER.name}")

    return bib_db


def update_structured_data(
    REVIEW_MANAGER, bib_db: BibDatabase, included: list
) -> BibDatabase:

    DATA = REVIEW_MANAGER.paths["DATA"]

    if not DATA.is_file():
        included = get_records_for_synthesis(bib_db)

        coding_dimensions_str = input(
            "Enter columns for data extraction (comma-separted)"
        )
        coding_dimensions = coding_dimensions_str.replace(" ", "_").split(",")

        data = []
        for included_id in included:
            item = [[included_id], ["TODO"] * len(coding_dimensions)]
            data.append(list(itertools.chain(*item)))

        data_df = pd.DataFrame(data, columns=["ID"] + coding_dimensions)
        data_df.sort_values(by=["ID"], inplace=True)

        with open(DATA, "w") as f:
            yaml.dump(
                json.loads(data_df.to_json(orient="records")),
                f,
                default_flow_style=False,
            )

    else:

        nr_records_added = 0

        with open(DATA) as f:
            data_df = pd.json_normalize(safe_load(f))

        for record_id in included:
            # skip when already available
            if 0 < len(data_df[data_df["ID"].str.startswith(record_id)]):
                continue

            add_record = pd.DataFrame({"ID": [record_id]})
            add_record = add_record.reindex(columns=data_df.columns, fill_value="TODO")
            data_df = pd.concat([data_df, add_record], axis=0, ignore_index=True)
            nr_records_added = nr_records_added + 1

        data_df.sort_values(by=["ID"], inplace=True)
        with open(DATA, "w") as f:
            yaml.dump(
                json.loads(data_df.to_json(orient="records")),
                f,
                default_flow_style=False,
            )

        report_logger.info(f"{nr_records_added} records added ({DATA})")
        logger.info(f"{nr_records_added} records added ({DATA})")

    return bib_db


def update_synthesized_status(REVIEW_MANAGER, bib_db):

    PAPER = REVIEW_MANAGER.paths["PAPER"]
    DATA = REVIEW_MANAGER.paths["DATA"]

    synthesized_in_manuscript = get_synthesized_ids(bib_db, PAPER)
    structured_data_extracted = get_structured_data_extracted(bib_db, DATA)

    DATA_FORMAT = REVIEW_MANAGER.config["DATA_FORMAT"]
    for record in bib_db.entries:
        if (
            "MANUSCRIPT" in DATA_FORMAT
            and record["ID"] not in synthesized_in_manuscript
        ):
            continue
        if (
            "STRUCTURED" in DATA_FORMAT
            and record["ID"] not in structured_data_extracted
        ):
            continue

        record.update(status=RecordState.rev_synthesized)
        report_logger.info(
            f' {record["ID"]}'.ljust(PAD, " ") + "set status to synthesized"
        )
        logger.info(f' {record["ID"]}'.ljust(PAD, " ") + "set status to synthesized")

    REVIEW_MANAGER.save_bib_db(bib_db)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

    return bib_db


def edit_csv(REVIEW_MANAGER) -> None:
    DATA = REVIEW_MANAGER.paths["DATA"]
    DATA_CSV = str(DATA).replace(".yaml", ".csv")
    if edit_csv:
        with open(DATA) as f:
            data_df = pd.json_normalize(safe_load(f))
            data_df.to_csv(DATA_CSV, index=False)
            report_logger.info(f"Created {DATA_CSV} based on {DATA}")
            logger.info(f"Created {DATA_CSV} based on {DATA}")
    return


def load_csv(REVIEW_MANAGER) -> None:
    DATA = REVIEW_MANAGER.paths["DATA"]
    DATA_CSV = str(DATA).replace(".yaml", ".csv")
    if load_csv:
        data_df = pd.read_csv(DATA_CSV)
        with open(DATA, "w") as f:
            yaml.dump(
                json.loads(data_df.to_json(orient="records")),
                f,
                default_flow_style=False,
            )
        report_logger.info(f"Loaded {DATA_CSV} into {DATA}")
        logger.info(f"Loaded {DATA_CSV} into {DATA}")
    return


def main(REVIEW_MANAGER) -> None:
    from review_template.review_manager import Process, ProcessType

    saved_args = locals()

    REVIEW_MANAGER.notify(Process(ProcessType.data))

    bib_db = REVIEW_MANAGER.load_bib_db()

    global PAD
    PAD = min((max(len(x["ID"]) for x in bib_db.entries) + 2), 35)

    included = get_records_for_synthesis(bib_db)

    if 0 == len(included):
        report_logger.info("No records included yet (use review_template screen)")
        logger.info("No records included yet (use review_template screen)")

    else:

        DATA_FORMAT = REVIEW_MANAGER.config["DATA_FORMAT"]
        git_repo = REVIEW_MANAGER.get_repo()
        if "MANUSCRIPT" in DATA_FORMAT:
            bib_db = update_manuscript(REVIEW_MANAGER, bib_db, included)
            git_repo.index.add([str(REVIEW_MANAGER.paths["PAPER_RELATIVE"])])
        if "STRUCTURED" in DATA_FORMAT:
            bib_db = update_structured_data(REVIEW_MANAGER, bib_db, included)
            git_repo.index.add([str(REVIEW_MANAGER.paths["DATA_RELATIVE"])])

        bib_db = update_synthesized_status(REVIEW_MANAGER, bib_db)

        if "y" == input("Create commit (y/n)?"):
            REVIEW_MANAGER.create_commit(
                "Data and synthesis", manual_author=True, saved_args=saved_args
            )

    return
