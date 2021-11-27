#! /usr/bin/env python
import json
import logging
import multiprocessing as mp
import os

import git
import requests
from bibtexparser.bibdatabase import BibDatabase
from pdfminer.high_level import extract_text

from review_template import dedupe
from review_template import grobid_client
from review_template import importer
from review_template import process
from review_template import repo_setup
from review_template import utils

# https://github.com/ContentMine/getpapers

PDF_DIRECTORY = repo_setup.paths["PDF_DIRECTORY"]
BATCH_SIZE = repo_setup.config["BATCH_SIZE"]

current_batch_counter = mp.Value("i", 0)
linked_existing_files = False


def unpaywall(doi: str, retry: int = 0, pdfonly: bool = True) -> str:

    r = requests.get(
        "https://api.unpaywall.org/v2/{doi}",
        params={"email": repo_setup.config["EMAIL"]},
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
                    logging.info("Retrieved pdf (unpaywall):" f" {pdf_filepath}")
                else:
                    os.remove(pdf_filepath)
            else:
                logging.info("Unpaywall retrieval error " f"{res.status_code}/{url}")
    return record


def link_pdf(record: dict) -> dict:
    global PAD
    if "PAD" not in globals():
        PAD = 40
    pdf_filepath = os.path.join(PDF_DIRECTORY, record["ID"] + ".pdf")
    if os.path.exists(pdf_filepath):
        record.update(pdf_status="imported")
        record.update(file=pdf_filepath)
        logging.info(f' {record["ID"]}'.ljust(PAD, " ") + "linked pdf")
    else:
        record.update(pdf_status="needs_manual_retrieval")
    return record


def retrieve_pdf(record: dict) -> dict:
    if "needs_retrieval" != record.get("pdf_status", "NA"):
        return record

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return record
        else:
            current_batch_counter.value += 1

    retrieval_scripts = {"get_pdf_from_unpaywall": get_pdf_from_unpaywall}

    for retrieval_script in retrieval_scripts:
        logging.debug(f'{retrieval_script}({record["ID"]}) called')
        record = retrieval_scripts[retrieval_script](record)

    record = get_pdf_from_unpaywall(record)

    record = link_pdf(record)

    return record


def get_missing_records(bib_db: BibDatabase) -> BibDatabase:
    missing_records = BibDatabase()
    for record in bib_db.entries:
        if record.get("pdf_status", "NA") in [
            "needs_retrieval",
            "needs_manual_retrieval",
        ]:
            missing_records.entries.append(record)
    return missing_records


def print_details(missing_records: BibDatabase) -> None:
    # TODO: instead of a global counter, compare prior/latter stats
    # like prepare/set_stats_beginning, print_stats_end
    # global pdfs_retrieved
    # if pdfs_retrieved > 0:
    #     logging.info(f'{pdfs_retrieved} PDFs retrieved')
    # else:
    #     logging.info('No PDFs retrieved')
    if len(missing_records.entries) > 0:
        logging.info(f"{len(missing_records.entries)} PDFs missing ")
    return


def get_pdfs_from_dir(directory: str) -> list:
    list_of_files = []
    for (dirpath, dirnames, filenames) in os.walk(directory):
        for filename in filenames:
            if filename.endswith(".pdf"):
                list_of_files.append(os.path.join(dirpath, filename))
    return list_of_files


def check_existing_unlinked_pdfs(bib_db: BibDatabase) -> BibDatabase:
    global linked_existing_files
    pdf_files = get_pdfs_from_dir(PDF_DIRECTORY)

    if not pdf_files:
        return bib_db

    logging.info("Starting GROBID service to extract metadata from PDFs")
    grobid_client.start_grobid()

    IDs = [x["ID"] for x in bib_db.entries]

    for file in pdf_files:
        if os.path.exists(os.path.basename(file).replace(".pdf", "")):
            continue
        if os.path.basename(file).replace(".pdf", "") not in IDs:
            db = importer.pdf2bib(file)
            corresponding_bib_file = file.replace(".pdf", ".bib")
            if os.path.exists(corresponding_bib_file):
                os.remove(corresponding_bib_file)

            if not db:
                continue

            record = db.entries[0]
            max_similarity = 0
            max_sim_record = None
            for bib_record in bib_db.entries:
                sim = dedupe.get_record_similarity(record, bib_record.copy())
                if sim > max_similarity:
                    max_similarity = sim
                    max_sim_record = bib_record

            if max_similarity > 0.5:
                if "prepared" == max_sim_record.get("pdf_status", "NA"):
                    continue
                new_filename = os.path.join(
                    os.path.dirname(file), max_sim_record["ID"] + ".pdf"
                )
                max_sim_record.update(file=new_filename)
                max_sim_record.update(pdf_status="imported")
                linked_existing_files = True
                os.rename(file, new_filename)
                logging.info("checked and renamed pdf:" f" {file} > {new_filename}")
                # max_sim_record = \
                #     pdf_prepare.validate_pdf_metadata(max_sim_record)
                # pdf_status = max_sim_record.get('pdf_status', 'NA')
                # if 'needs_manual_preparation' == pdf_status:
                #     # revert?

    return bib_db


def main(bib_db: BibDatabase, repo: git.Repo) -> BibDatabase:
    global linked_existing_files
    saved_args = locals()

    utils.require_clean_repo(repo, ignore_pattern=PDF_DIRECTORY)
    process.check_delay(bib_db, min_status_requirement="pdf_needs_retrieval")
    global PAD
    PAD = min((max(len(x["ID"]) for x in bib_db.entries) + 2), 35)
    print("TODO: download if there is a fulltext link in the record")
    if not os.path.exists(PDF_DIRECTORY):
        os.mkdir(PDF_DIRECTORY)

    utils.reset_log()
    logging.info("Retrieve PDFs")

    bib_db = check_existing_unlinked_pdfs(bib_db)

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logging.info("Continuing batch preparation started earlier")

        pool = mp.Pool(repo_setup.config["CPUS"])
        bib_db.entries = pool.map(retrieve_pdf, bib_db.entries)
        pool.close()
        pool.join()

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        missing_records = get_missing_records(bib_db)

        if batch_end > 0 or linked_existing_files:
            logging.info(
                "Completed pdf retrieval batch "
                f"(records {batch_start} to {batch_end})"
            )

            print_details(missing_records)

            MAIN_REFERENCES = repo_setup.paths["MAIN_REFERENCES"]
            utils.save_bib_file(bib_db, MAIN_REFERENCES)
            repo.index.add([MAIN_REFERENCES])

            if "GIT" == repo_setup.config["PDF_HANDLING"]:
                if os.path.exists(PDF_DIRECTORY):
                    for record in bib_db.entries:
                        filepath = os.path.join(PDF_DIRECTORY, record["ID"] + ".pdf")
                        if os.path.exists(filepath):
                            repo.index.add([filepath])

            in_process = utils.create_commit(repo, "⚙️ Retrieve PDFs", saved_args)

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logging.info("No additional pdfs to retrieve")
            break

    return bib_db
