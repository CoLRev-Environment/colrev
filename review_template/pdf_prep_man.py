#! /usr/bin/env python
import logging

from bibtexparser.bibdatabase import BibDatabase

from review_template import pdf_prepare


def man_prep_pdf(record: dict) -> dict:

    for prep_script in pdf_prepare.prep_scripts:
        logging.debug(f'{prep_script}({record["ID"]}) called')
        record = pdf_prepare.prep_scripts[prep_script](record)
        print(
            "TODO: check /print problems for each PDF with pdf_status = "
            "needs_manual_preparation and suggest how it could be fixed"
        )

    return record


def main(REVIEW_MANAGER) -> BibDatabase:
    saved_args = locals()

    global PDF_DIRECTORY
    PDF_DIRECTORY = REVIEW_MANAGER.paths["PDF_DIRECTORY"]

    bib_db = REVIEW_MANAGER.load_main_refs()
    for record in bib_db.entries:
        record = man_prep_pdf(record)

    return bib_db
