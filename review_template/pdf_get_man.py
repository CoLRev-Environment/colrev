#! /usr/bin/env python
import csv
import logging
import multiprocessing as mp
import os
import urllib.parse
import webbrowser

import pandas as pd
from bibtexparser.bibdatabase import BibDatabase

from review_template import pdfs

existing_pdfs_linked = 0

# https://github.com/ContentMine/getpapers

PDF_DIRECTORY = "NA"
BATCH_SIZE = -1

current_batch_counter = mp.Value("i", 0)


def export_retrieval_table(missing_records: list) -> None:
    if len(missing_records.entries) > 0:
        missing_records_df = pd.DataFrame.from_records(missing_records.entries)
        col_order = [
            "ID",
            "author",
            "title",
            "journal",
            "booktitle",
            "year",
            "volume",
            "number",
            "pages",
            "doi",
        ]
        missing_records_df = missing_records_df.reindex(col_order, axis=1)
        missing_records_df.to_csv(
            "missing_pdf_files.csv", index=False, quoting=csv.QUOTE_ALL
        )

        logging.info("Created missing_pdf_files.csv with paper details")
    return


def get_pdf_from_google(record: dict) -> dict:
    title = record["title"]
    title = urllib.parse.quote_plus(title)
    url = f"https://www.google.com/search?q={title}+filetype%3Apdf"
    webbrowser.open_new_tab(url)
    return record


def get_pdf_from_author_email(record: dict) -> dict:
    webbrowser.open("mailto:author_mail", new=1)
    # Note: does not seem to work with chrome...
    # ?subject=Your paper&body=Hi, can you share paper x?
    return record


def man_retrieve(record: dict) -> dict:
    retrieval_scripts = {
        "get_pdf_from_google": get_pdf_from_google,
        "get_pdf_from_author_email": get_pdf_from_author_email,
    }
    #  'get_pdf_from_researchgate': get_pdf_from_researchgate,

    for retrieval_script in retrieval_scripts:
        logging.debug(f'{retrieval_script}({record["ID"]}) called')
        record = retrieval_scripts[retrieval_script](record)
        if "y" == input("Retrieved (y/n)?"):
            break

    return record


def main(review_manager) -> BibDatabase:
    saved_args = locals()

    global PDF_DIRECTORY
    global BATCH_SIZE

    PDF_DIRECTORY = review_manager.paths["PDF_DIRECTORY"]
    BATCH_SIZE = review_manager.config["BATCH_SIZE"]

    logging.info("Get PDFs manually")

    bib_db = review_manager.load_main_refs()
    bib_db = pdfs.check_existing_unlinked_pdfs(bib_db)
    for record in bib_db.entries:
        record = pdfs.link_pdf(record)

    missing_records = pdfs.get_missing_records(bib_db)
    export_retrieval_table(missing_records)

    if "y" == input("Start retrieval process (y/n)?"):
        for record in bib_db.entries:
            record = man_retrieve(record)

    MAIN_REFERENCES = review_manager.paths["MAIN_REFERENCES"]
    review_manager.save_bib_file(bib_db, MAIN_REFERENCES)
    git_repo = review_manager.get_repo()
    git_repo.index.add([MAIN_REFERENCES])

    if "GIT" == review_manager.config["PDF_HANDLING"]:
        if os.path.exists(PDF_DIRECTORY):
            for record in bib_db.entries:
                filepath = os.path.join(PDF_DIRECTORY, record["ID"] + ".pdf")
                if os.path.exists(filepath):
                    git_repo.index.add([filepath])

    if git_repo.is_dirty():
        if "y" == input("Create commit (y/n)?"):
            review_manager.create_commit(
                "Get PDFs manually", saved_args, manual_author=True
            )
    else:
        logging.info(
            "Retrieve PDFs manually and copy the files to "
            f"the {PDF_DIRECTORY}. Afterwards, use "
            "review_template pdf-get-man"
        )

    return bib_db
