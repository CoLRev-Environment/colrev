#! /usr/bin/env python
import itertools
import json
import logging
import re
import tempfile
import typing
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml
from yaml import safe_load

from colrev_core import review_manager
from colrev_core.review_manager import RecordState

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")

PAD = 0


def get_records_for_synthesis(records: typing.List[dict]) -> list:
    return [
        x["ID"]
        for x in records
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


def get_synthesized_ids(records: typing.List[dict], PAPER: Path) -> list:

    records_for_synthesis = get_records_for_synthesis(records)

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


def get_structured_data_extracted(records: typing.List[dict], DATA: Path) -> list:

    if not DATA.is_dir():
        return []

    records_for_data_extraction = [
        x["ID"]
        for x in records
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
                    writer.write(missing_record)
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
                writer.write(missing_record)
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
        # author = git_repo.git.show("-s", "--format=%an", commit.hexsha)
        # mail = git_repo.git.show("-s", "--format=%ae", commit.hexsha)
    author = ", ".join(dict(Counter(commits_authors)))
    return author


def update_manuscript(
    REVIEW_MANAGER, records: typing.List[dict], included: list
) -> typing.List[dict]:

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

        PAPER_resource_path = Path("template/") / PAPER_RELATIVE
        review_manager.retrieve_package_file(PAPER_resource_path, PAPER)
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
        add_missing_records_to_manuscript(
            PAPER,
            ["\n- @" + missing_record + "\n" for missing_record in missing_records],
        )
        nr_records_added = len(missing_records)
        report_logger.info(f"{nr_records_added} records added to {PAPER.name}")
        logger.info(f"{nr_records_added} records added to {PAPER.name}")

    return records


def update_structured_data(
    REVIEW_MANAGER, records: typing.List[dict], included: list
) -> typing.List[dict]:

    DATA = REVIEW_MANAGER.paths["DATA"]

    if not DATA.is_file():
        included = get_records_for_synthesis(records)

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

    return records


def update_synthesized_status(REVIEW_MANAGER, records: typing.List[dict]):

    PAPER = REVIEW_MANAGER.paths["PAPER"]
    DATA = REVIEW_MANAGER.paths["DATA"]

    synthesized_in_manuscript = get_synthesized_ids(records, PAPER)
    structured_data_extracted = get_structured_data_extracted(records, DATA)

    DATA_FORMAT = REVIEW_MANAGER.config["DATA_FORMAT"]
    for record in records:
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

    REVIEW_MANAGER.save_records(records)
    REVIEW_MANAGER.add_record_changes()

    return records


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


def update_tei(
    REVIEW_MANAGER, records: typing.List[dict], included: typing.List[dict]
) -> typing.List[dict]:
    from colrev_core import grobid_client, tei_tools, dedupe
    import requests
    from lxml import etree
    from lxml.etree import XMLSyntaxError

    grobid_client.start_grobid()
    git_repo = REVIEW_MANAGER.get_repo()
    ns = {
        "tei": "{http://www.tei-c.org/ns/1.0}",
        "w3": "{http://www.w3.org/XML/1998/namespace}",
    }

    for record in records:
        if "file" not in record:
            continue
        if "tei_file" not in record:
            logger.info(f"Get tei for {record['ID']}")
            fpath = REVIEW_MANAGER.paths["REPO_DIR"] / record["file"]
            tei_path = Path(record["file"].replace("pdfs/", "tei/")).with_suffix(
                ".tei.xml"
            )
            tei_path = (
                REVIEW_MANAGER.paths["REPO_DIR"]
                / Path("tei")
                / Path(record["ID"] + ".tei.xml")
            )
            tei_path.parents[0].mkdir(exist_ok=True)
            record["tei_file"] = str(tei_path)
            if tei_path.is_file():
                continue

            try:
                options = {}
                # options["consolidateCitations"] = "1"
                options["consolidateCitations"] = "0"
                r = requests.post(
                    grobid_client.get_grobid_url() + "/api/processFulltextDocument",
                    files={"input": open(str(fpath), "rb")},
                    data=options,
                )
                data = r.content
                if b"[TIMEOUT]" in data:
                    del record["tei_file"]
                    continue
                with open(tei_path, "wb") as tf:
                    tf.write(data)

                with open(record["tei_file"], "rb") as tf:
                    xml_string = tf.read()
                root = etree.fromstring(xml_string)
                tree = etree.ElementTree(root)
                tree.write(record["tei_file"], pretty_print=True, encoding="utf-8")

                if tei_path.is_file():
                    git_repo.index.add([str(tei_path)])

            except etree.XMLSyntaxError:
                del record["tei_file"]
                pass
    # TODO : only create a commit if there are changes.
    REVIEW_MANAGER.save_records(records)
    REVIEW_MANAGER.add_record_changes()
    # REVIEW_MANAGER.create_commit("Create TEIs")

    # Enhance TEIs (link local IDs)
    for record in records:
        logger.info(f"Enhance TEI for {record['ID']}")
        if "tei_file" in record:
            tei_path = Path(record["tei_file"])

            try:
                with open(tei_path, "rb") as tf:
                    xml_string = tf.read()
                root = etree.fromstring(xml_string)
                tei_records = tei_tools.get_bibliography(root)
            except XMLSyntaxError:
                pass
                continue

            for record in tei_records:
                if "title" not in record:
                    continue

                max_sim = 0.8
                max_sim_record = {}
                for local_record in records:
                    if local_record["status"] not in [
                        RecordState.rev_included,
                        RecordState.rev_synthesized,
                    ]:
                        continue
                    rec_sim = dedupe.get_record_similarity(
                        record.copy(), local_record.copy()
                    )
                    if rec_sim > max_sim:
                        max_sim_record = local_record
                        max_sim = rec_sim

                if len(max_sim_record) == 0:
                    continue

                # Record found: mark in tei
                bibliography = root.find(".//" + ns["tei"] + "listBibl")
                for ref in bibliography:
                    if ref.get(ns["w3"] + "id") == record["ID"]:
                        ref.set("ID", max_sim_record["ID"])
                for reference in root.iter(ns["tei"] + "ref"):
                    if "target" in reference.keys():
                        if reference.get("target") == f"#{record['ID']}":
                            reference.set("ID", max_sim_record["ID"])

                # if settings file available: dedupe_io match agains records

            # theories = ['actornetwork theory', 'structuration theory']
            # for paragraph in root.iter(ns['tei'] + 'p'):
            #     # print(paragraph.text.lower())
            #     for theory in theories:
            #         # if theory in ''.join(paragraph.itertext()):
            #         if theory in paragraph.text:
            #             paragraph.text = \
            #               paragraph.text.replace(theory, f'<theory>{theory}</theory>')

            tree = etree.ElementTree(root)
            tree.write(str(tei_path), pretty_print=True, encoding="utf-8")

            # if tei_path.is_file():
            #     git_repo.index.add([str(tei_path)])

    # REVIEW_MANAGER.create_commit("Enhance TEIs")

    return records


def enlit_heuristic(REVIEW_MANAGER):

    from colrev_core.review_manager import Process, ProcessType

    REVIEW_MANAGER.notify(Process(ProcessType.explore))

    # TODO : warn if teis are missing for some files
    tei_path = REVIEW_MANAGER.paths["REPO_DIR"] / Path("tei")

    enlit_list = []
    records = REVIEW_MANAGER.load_records()
    relevant_records = get_records_for_synthesis(records)
    for relevant_record in relevant_records:
        enlit_status = str(
            [x["status"] for x in records if x["ID"] == relevant_record].pop()
        )
        enlit_status = enlit_status.replace("rev_included", "").replace(
            "rev_synthesized", "synthesized"
        )
        enlit_list.append(
            {
                "ID": relevant_record,
                "score": 0,
                "score_intensity": 0,
                "status": enlit_status,
            }
        )

    for tei_file in tei_path.glob("*.tei.xml"):
        data = tei_file.read_text()
        for enlit_item in enlit_list:
            ID_string = f'ID="{enlit_item["ID"]}"'
            if ID_string in data:
                enlit_item["score"] += 1
            enlit_item["score_intensity"] += data.count(ID_string)

    enlit_list = sorted(enlit_list, key=lambda d: d["score"], reverse=True)

    return enlit_list


def main(REVIEW_MANAGER) -> None:
    from colrev_core.review_manager import Process, ProcessType

    saved_args = locals()

    REVIEW_MANAGER.notify(Process(ProcessType.data))

    records = REVIEW_MANAGER.load_records()

    global PAD
    PAD = min((max(len(x["ID"]) for x in records) + 2), 35)

    included = get_records_for_synthesis(records)

    if 0 == len(included):
        report_logger.info("No records included yet (use colrev_core screen)")
        logger.info("No records included yet (use colrev_core screen)")

    else:

        DATA_FORMAT = REVIEW_MANAGER.config["DATA_FORMAT"]
        git_repo = REVIEW_MANAGER.get_repo()
        if "TEI" in DATA_FORMAT:
            records = update_tei(REVIEW_MANAGER, records, included)
            REVIEW_MANAGER.save_records(records)
            REVIEW_MANAGER.add_record_changes()
        if "MANUSCRIPT" in DATA_FORMAT:
            records = update_manuscript(REVIEW_MANAGER, records, included)
            git_repo.index.add([str(REVIEW_MANAGER.paths["PAPER_RELATIVE"])])
        if "STRUCTURED" in DATA_FORMAT:
            records = update_structured_data(REVIEW_MANAGER, records, included)
            git_repo.index.add([str(REVIEW_MANAGER.paths["DATA_RELATIVE"])])

        # records = update_synthesized_status(REVIEW_MANAGER, records)

        if "y" == input("Create commit (y/n)?"):
            REVIEW_MANAGER.create_commit(
                "Data and synthesis", manual_author=True, saved_args=saved_args
            )

    return
