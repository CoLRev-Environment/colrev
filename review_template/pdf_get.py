#! /usr/bin/env python
import json
import logging
import multiprocessing as mp
import os

import requests
from bibtexparser.bibdatabase import BibDatabase
from pdfminer.high_level import extract_text

from review_template import dedupe
from review_template import grobid_client
from review_template import tei_tools
from review_template.review_manager import RecordState

logger = logging.getLogger("review_template")

# https://github.com/ContentMine/getpapers

PDF_DIRECTORY, BATCH_SIZE, EMAIL = "NA", -1, "NA"

current_batch_counter = mp.Value("i", 0)
linked_existing_files = False


def unpaywall(doi: str, retry: int = 0, pdfonly: bool = True) -> str:

    r = requests.get(
        "https://api.unpaywall.org/v2/{doi}",
        params={"email": EMAIL},
    )

    if r.status_code == 404:
        return None

    if r.status_code == 500:
        if retry < 3:
            return unpaywall(doi, retry + 1)
        else:
            return None

    best_loc = None
    try:
        best_loc = r.json()["best_oa_location"]
    except json.decoder.JSONDecodeError:
        return None
    except KeyError:
        return None

    if not r.json()["is_oa"] or best_loc is None:
        return None

    if best_loc["url_for_pdf"] is None and pdfonly is True:
        return None
    else:
        return best_loc["url_for_pdf"]


def is_pdf(path_to_file: str) -> bool:
    try:
        extract_text(path_to_file)
        return True
    except:  # noqa E722
        return False


def get_pdf_from_unpaywall(record: dict) -> dict:
    if "doi" not in record:
        return record

    pdf_filepath = os.path.join(PDF_DIRECTORY, record["ID"] + ".pdf")
    url = unpaywall(record["doi"])
    if url is not None:
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
                    logger.info("Retrieved pdf (unpaywall):" f" {pdf_filepath}")
                else:
                    os.remove(pdf_filepath)
            else:
                logger.info("Unpaywall retrieval error " f"{res.status_code}/{url}")
    return record


def link_pdf(
    record: dict, PDF_DIRECTORY: str, set_needs_man_retrieval: bool = True
) -> dict:
    global PAD
    if "PAD" not in globals():
        PAD = 40
    pdf_filepath = os.path.join(PDF_DIRECTORY, record["ID"] + ".pdf")
    if os.path.exists(pdf_filepath) and pdf_filepath != record.get("file", "NA"):
        record.update(status=RecordState.pdf_imported)
        record.update(file=pdf_filepath)
        logger.info(f' {record["ID"]}'.ljust(PAD, " ") + "linked pdf")
    else:
        if set_needs_man_retrieval:
            record.update(status=RecordState.pdf_needs_manual_retrieval)
    return record


def retrieve_pdf(record: dict) -> dict:
    if RecordState.rev_prescreen_included != record["status"]:
        return record

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return record
        else:
            current_batch_counter.value += 1

    retrieval_scripts = {"get_pdf_from_unpaywall": get_pdf_from_unpaywall}

    for retrieval_script in retrieval_scripts:
        logger.debug(f'{retrieval_script}({record["ID"]}) called')
        record = retrieval_scripts[retrieval_script](record)

    record = get_pdf_from_unpaywall(record)

    record = link_pdf(record, PDF_DIRECTORY)

    return record


def get_missing_records(bib_db: BibDatabase) -> BibDatabase:
    missing_records = BibDatabase()
    for record in bib_db.entries:
        if record["status"] in [
            RecordState.rev_prescreen_included,
            RecordState.pdf_needs_manual_retrieval,
        ]:
            missing_records.entries.append(record)
    return missing_records


def print_details(missing_records: BibDatabase) -> None:
    # TODO: instead of a global counter, compare prior/latter stats
    # like prepare/set_stats_beginning, print_stats_end
    # global pdfs_retrieved
    # if pdfs_retrieved > 0:
    #     logger.info(f'{pdfs_retrieved} PDFs retrieved')
    # else:
    #     logger.info('No PDFs retrieved')
    if len(missing_records.entries) > 0:
        logger.info(f"{len(missing_records.entries)} PDFs missing ")
    return


def get_pdfs_from_dir(directory: str) -> list:
    list_of_files = []
    for (dirpath, dirnames, filenames) in os.walk(directory):
        for filename in filenames:
            if filename.endswith(".pdf"):
                list_of_files.append(os.path.join(dirpath, filename))
    return list_of_files


def check_existing_unlinked_pdfs(
    bib_db: BibDatabase, PDF_DIRECTORY: str
) -> BibDatabase:
    global linked_existing_files
    pdf_files = get_pdfs_from_dir(PDF_DIRECTORY)
    if not pdf_files:
        return bib_db

    logger.info("Starting GROBID service to extract metadata from PDFs")
    grobid_client.start_grobid()

    IDs = [x["ID"] for x in bib_db.entries]

    for file in pdf_files:
        if os.path.basename(file).replace(".pdf", "") not in IDs:

            pdf_record = tei_tools.get_record_from_pdf_tei(file)

            if "error" in pdf_record:
                continue

            max_similarity = 0
            max_sim_record = None
            for record in bib_db.entries:
                sim = dedupe.get_record_similarity(pdf_record, record.copy())
                if sim > max_similarity:
                    max_similarity = sim
                    max_sim_record = record

            if max_similarity > 0.5:
                if RecordState.pdf_prepared == max_sim_record["status"]:
                    continue
                new_filename = os.path.join(
                    os.path.dirname(file), max_sim_record["ID"] + ".pdf"
                )
                max_sim_record.update(file=new_filename)
                max_sim_record.update(status=RecordState.pdf_imported)
                linked_existing_files = True
                os.rename(file, new_filename)
                logger.info("checked and renamed pdf:" f" {file} > {new_filename}")
                # max_sim_record = \
                #     pdf_prepare.validate_pdf_metadata(max_sim_record)
                # status = max_sim_record['status']
                # if RecordState.pdf_needs_manual_preparation == status:
                #     # revert?

    return bib_db


def main(REVIEW_MANAGER) -> None:
    global linked_existing_files
    saved_args = locals()

    global PDF_DIRECTORY
    global BATCH_SIZE
    global EMAIL
    EMAIL = REVIEW_MANAGER.config["EMAIL"]
    PDF_DIRECTORY = REVIEW_MANAGER.paths["PDF_DIRECTORY"]
    BATCH_SIZE = REVIEW_MANAGER.config["BATCH_SIZE"]

    bib_db = REVIEW_MANAGER.load_main_refs()

    global PAD
    PAD = min((max(len(x["ID"]) for x in bib_db.entries) + 2), 35)
    print("TODO: download if there is a fulltext link in the record")
    if not os.path.exists(PDF_DIRECTORY):
        os.mkdir(PDF_DIRECTORY)

    logger.info("Retrieve PDFs")

    bib_db = check_existing_unlinked_pdfs(bib_db, PDF_DIRECTORY)

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logger.info("Continuing batch preparation started earlier")

        pool = mp.Pool(REVIEW_MANAGER.config["CPUS"])
        bib_db.entries = pool.map(retrieve_pdf, bib_db.entries)
        pool.close()
        pool.join()

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        missing_records = get_missing_records(bib_db)

        if batch_end > 0 or linked_existing_files:
            logger.info(
                "Completed pdf retrieval batch "
                f"(records {batch_start} to {batch_end})"
            )

            print_details(missing_records)

            MAIN_REFERENCES = REVIEW_MANAGER.paths["MAIN_REFERENCES"]
            REVIEW_MANAGER.save_bib_file(bib_db)
            git_repo = REVIEW_MANAGER.get_repo()
            git_repo.index.add([MAIN_REFERENCES])

            if "GIT" == REVIEW_MANAGER.config["PDF_HANDLING"]:
                if os.path.exists(PDF_DIRECTORY):
                    for record in bib_db.entries:
                        filepath = os.path.join(PDF_DIRECTORY, record["ID"] + ".pdf")
                        if os.path.exists(filepath):
                            git_repo.index.add([filepath])

            in_process = REVIEW_MANAGER.create_commit(
                "Retrieve PDFs", saved_args=saved_args
            )

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logger.info("No additional pdfs to retrieve")
            break

    return
