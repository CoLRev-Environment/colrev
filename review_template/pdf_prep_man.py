#! /usr/bin/env python
import logging

from review_template import pdf_prepare
from review_template import repo_setup
from review_template import status
from review_template import utils

PDF_DIRECTORY = repo_setup.paths['PDF_DIRECTORY']


def man_prep_pdf(record):

    for prep_script in pdf_prepare.prep_scripts:
        logging.debug(f'{prep_script}({record["ID"]}) called')
        record = pdf_prepare.prep_scripts[prep_script](record)
        print('TODO: check /print problems for each PDF with pdf_status = '
              'needs_manual_preparation and suggest how it could be fixed')

    return record


def main(bib_db, repo):
    saved_args = locals()

    utils.require_clean_repo(repo, ignore_pattern=PDF_DIRECTORY)
    # process.check_delay(bib_db, min_status_requirement='pdf_needs_retrieval')

    utils.reset_log()

    for record in bib_db.entries:
        record = man_prep_pdf(record)

    status.review_instructions()
    return bib_db
