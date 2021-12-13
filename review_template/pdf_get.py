#! /usr/bin/env python
import json
import logging
import os
import pprint
from pathlib import Path

import requests
from bibtexparser.bibdatabase import BibDatabase
from pdfminer.high_level import extract_text
from tqdm.contrib.concurrent import process_map

from review_template import dedupe
from review_template import grobid_client
from review_template import tei_tools
from review_template.review_manager import RecordState

pp = pprint.PrettyPrinter(indent=4, width=140)


report_logger = logging.getLogger("review_template_report")
logger = logging.getLogger("review_template")

# https://github.com/ContentMine/getpapers

EMAIL = "NA"


def unpaywall(doi: str, retry: int = 0, pdfonly: bool = True) -> str:

    url = "https://api.unpaywall.org/v2/{doi}"

    r = requests.get(url, params={"email": EMAIL})

    if r.status_code == 404:
        return "NA"

    if r.status_code == 500:
        if retry < 3:
            return unpaywall(doi, retry + 1)
        else:
            return "NA"

    best_loc = None
    try:
        best_loc = r.json()["best_oa_location"]
    except json.decoder.JSONDecodeError:
        return "NA"
    except KeyError:
        return "NA"

    if not r.json()["is_oa"] or best_loc is None:
        return "NA"

    if best_loc["url_for_pdf"] is None and pdfonly is True:
        return "NA"
    else:
        return best_loc["url_for_pdf"]


def is_pdf(path_to_file: str) -> bool:
    try:
        extract_text(path_to_file)
        return True
    except:  # noqa E722
        return False


def get_pdf_from_unpaywall(item: dict, REVIEW_MANAGER) -> dict:
    record = item["record"]

    if "doi" not in record:
        return record

    pdf_filepath = (
        REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"] / f"{record['ID']}.pdf"
    )
    url = unpaywall(record["doi"])
    if "NA" != url:
        if "Invalid/unknown DOI" not in url:
            res = requests.get(
                url,
                headers={
                    "User-Agent": "Chrome/51.0.2704.103",
                    "referer": "https://www.doi.org",
                },
            )
            if 200 == res.status_code:
                with open(pdf_filepath, "wb") as f:
                    f.write(res.content)
                if is_pdf(pdf_filepath):
                    report_logger.info(
                        "Retrieved pdf (unpaywall):" f" {pdf_filepath.name}"
                    )
                    logger.info("Retrieved pdf (unpaywall):" f" {pdf_filepath.name}")
                    record.update(file=str(pdf_filepath))
                    record.update(status=RecordState.rev_prescreen_included)
                else:
                    os.remove(pdf_filepath)
            else:
                logger.info("Unpaywall retrieval error " f"{res.status_code}/{url}")
    return record


def link_pdf(item: dict, REVIEW_MANAGER) -> dict:
    record = item["record"]
    PDF_DIRECTORY_RELATIVE = REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]
    pdf_filepath = PDF_DIRECTORY_RELATIVE / f"{record['ID']}.pdf"
    if pdf_filepath.is_file() and str(pdf_filepath) != record.get("file", "NA"):
        record.update(file=str(pdf_filepath))

    return record


retrieval_scripts = {
    "get_pdf_from_unpaywall": get_pdf_from_unpaywall,
    "link_pdf": link_pdf,
}


def retrieve_pdf(item: dict) -> dict:
    record = item["record"]

    if str(RecordState.rev_prescreen_included) != str(record["status"]):
        return record

    REVIEW_MANAGER = item["REVIEW_MANAGER"]

    for retrieval_script in retrieval_scripts:
        report_logger.info(f'{retrieval_script}({record["ID"]}) called')
        record = retrieval_scripts[retrieval_script](item, REVIEW_MANAGER)
        if "file" in record:
            report_logger.info(
                f'{retrieval_script}({record["ID"]}): retrieved {record["file"]}'
            )
            record.update(status=RecordState.pdf_imported)
        else:
            record.update(status=RecordState.pdf_needs_manual_retrieval)

    return record


def add_to_git(REVIEW_MANAGER, retrieval_batch) -> None:
    git_repo = REVIEW_MANAGER.get_repo()
    if "GIT" == REVIEW_MANAGER.config["PDF_HANDLING"]:
        if REVIEW_MANAGER.paths["PDF_DIRECTORY"].is_dir():
            for record in retrieval_batch:
                if "file" in record:
                    if Path(record["file"]).is_file():
                        git_repo.index.add([record["file"]])

    return


def check_existing_unlinked_pdfs(
    REVIEW_MANAGER,
    bib_db: BibDatabase,
) -> BibDatabase:

    report_logger.info("Starting GROBID service to extract metadata from PDFs")
    logger.info("Starting GROBID service to extract metadata from PDFs")
    grobid_client.start_grobid()

    IDs = [x["ID"] for x in bib_db.entries]

    pdf_files = Path(REVIEW_MANAGER.paths["PDF_DIRECTORY"]).glob("*.pdf")
    for file in pdf_files:
        if file.stem not in IDs:

            pdf_record = tei_tools.get_record_from_pdf_tei(file)

            if "error" in pdf_record:
                continue

            max_similarity = 0.0
            max_sim_record = None
            for record in bib_db.entries:
                sim = dedupe.get_record_similarity(pdf_record, record.copy())
                if sim > max_similarity:
                    max_similarity = sim
                    max_sim_record = record
            if max_sim_record:
                if max_similarity > 0.5:
                    if RecordState.pdf_prepared == max_sim_record["status"]:
                        continue
                    new_filename = (
                        REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]
                        / f"{max_sim_record['ID']}.pdf"
                    )

                    max_sim_record.update(file=str(new_filename))
                    max_sim_record.update(status=RecordState.pdf_imported)
                    file.rename(new_filename)
                    report_logger.info(
                        "checked and renamed pdf:" f" {file.name} > {new_filename.name}"
                    )
                    logger.info(
                        "checked and renamed pdf:" f" {file.name} > {new_filename.name}"
                    )
                    # max_sim_record = \
                    #     pdf_prepare.validate_pdf_metadata(max_sim_record)
                    # status = max_sim_record['status']
                    # if RecordState.pdf_needs_manual_preparation == status:
                    #     # revert?

    return bib_db


def get_data(REVIEW_MANAGER) -> dict:
    from review_template.review_manager import RecordState

    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [
            x
            for x in record_state_list
            if str(RecordState.rev_prescreen_included) == x[1]
        ]
    )

    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)
    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": str(RecordState.rev_prescreen_included)},
    )

    prep_data = {
        "nr_tasks": nr_tasks,
        "PAD": PAD,
        "items": items,
    }
    logger.debug(pp.pformat(prep_data))
    return prep_data


def batch(items, REVIEW_MANAGER):
    n = REVIEW_MANAGER.config["BATCH_SIZE"]
    batch = []
    for item in items:
        batch.append(
            {
                "record": item,
                "REVIEW_MANAGER": REVIEW_MANAGER,
            }
        )
        if len(batch) == n:
            yield batch
            batch = []
    yield batch


def main(REVIEW_MANAGER) -> None:

    saved_args = locals()

    print("TODO: download if there is a fulltext link in the record")

    global EMAIL
    EMAIL = REVIEW_MANAGER.config["EMAIL"]
    CPUS = REVIEW_MANAGER.config["CPUS"]

    PDF_DIRECTORY = REVIEW_MANAGER.paths["PDF_DIRECTORY"]
    PDF_DIRECTORY.mkdir(exist_ok=True)

    report_logger.info("Retrieve PDFs")
    logger.info("Retrieve PDFs")

    bib_db = REVIEW_MANAGER.load_bib_db()
    bib_db = check_existing_unlinked_pdfs(REVIEW_MANAGER, bib_db)

    pdf_get_data = get_data(REVIEW_MANAGER)
    logger.debug(f"pdf_get_data: {pp.pformat(pdf_get_data)}")

    logger.debug(pp.pformat(pdf_get_data["items"]))

    try:
        from local_paper_index import retrieve

        retrieval_scripts["get_pdf_from_local_index"] = retrieve.individual_record
    except ImportError as e:
        logger.debug(e)
        pass

    i = 1
    for retrieval_batch in batch(pdf_get_data["items"], REVIEW_MANAGER):

        print(f"Batch {i}")
        i += 1

        retrieval_batch = process_map(retrieve_pdf, retrieval_batch, max_workers=CPUS)

        REVIEW_MANAGER.save_record_list_by_ID(retrieval_batch)

        # Multiprocessing mixes logs of different records.
        # For better readability:
        REVIEW_MANAGER.reorder_log([x["ID"] for x in retrieval_batch])

        add_to_git(REVIEW_MANAGER, retrieval_batch)

        REVIEW_MANAGER.create_commit("Retrieve PDFs", saved_args=saved_args)

    if i == 1:
        logger.info("No additional pdfs to retrieve")

    return
