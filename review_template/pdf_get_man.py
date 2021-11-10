#! /usr/bin/env python
import csv
import logging
import multiprocessing as mp
import os
import urllib.parse
import webbrowser

import pandas as pd

from review_template import pdfs
from review_template import repo_setup
from review_template import status
from review_template import utils

existing_pdfs_linked = 0

# https://github.com/ContentMine/getpapers

PDF_DIRECTORY = repo_setup.paths['PDF_DIRECTORY']
BATCH_SIZE = repo_setup.config['BATCH_SIZE']

current_batch_counter = mp.Value('i', 0)


def export_retrieval_table(missing_records):
    if len(missing_records.entries) > 0:
        missing_records_df = pd.DataFrame.from_records(missing_records.entries)
        col_order = [
            'ID', 'author', 'title', 'journal', 'booktitle',
            'year', 'volume', 'number', 'pages', 'doi'
        ]
        missing_records_df = missing_records_df.reindex(col_order, axis=1)
        missing_records_df.to_csv('missing_pdf_files.csv',
                                  index=False, quoting=csv.QUOTE_ALL)

        logging.info('Created missing_pdf_files.csv with paper details')
    return


def get_pdf_from_google(record):
    title = record['title']
    title = urllib.parse.quote_plus(title)
    url = f'https://www.google.com/search?q={title}+filetype%3Apdf'
    webbrowser.open_new_tab(url)
    return record


def get_pdf_from_author_email(record):
    webbrowser.open('mailto:author_mail', new=1)
    # Note: does not seem to work with chrome...
    # ?subject=Your paper&body=Hi, can you share paper x?
    return record


def man_retrieve(record):
    retrieval_scripts = \
        {'get_pdf_from_google': get_pdf_from_google,
         'get_pdf_from_author_email': get_pdf_from_author_email}
    #  'get_pdf_from_researchgate': get_pdf_from_researchgate,

    for retrieval_script in retrieval_scripts:
        logging.debug(f'{retrieval_script}({record["ID"]}) called')
        record = retrieval_scripts[retrieval_script](record)
        if 'y' == input('Retrieved (y/n)?'):
            break

    return record


def main(bib_db, repo):
    saved_args = locals()

    utils.require_clean_repo(repo, ignore_pattern=PDF_DIRECTORY)
    # process.check_delay(bib_db, min_status_requirement='pdf_needs_retrieval')

    utils.reset_log()
    logging.info('Get PDFs manually')

    bib_db = pdfs.check_existing_unlinked_pdfs(bib_db)
    for record in bib_db.entries:
        record = pdfs.link_pdf(record)

    missing_records = pdfs.get_missing_records(bib_db)
    export_retrieval_table(missing_records)

    if 'y' == input('Start retrieval process (y/n)?'):
        for record in bib_db.entries:
            record = man_retrieve(record)

    MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
    utils.save_bib_file(bib_db, MAIN_REFERENCES)
    repo.index.add([MAIN_REFERENCES])

    if 'GIT' == repo_setup.config['PDF_HANDLING']:
        if os.path.exists(PDF_DIRECTORY):
            for record in bib_db.entries:
                filepath = os.path.join(PDF_DIRECTORY,
                                        record['ID'] + '.pdf')
                if os.path.exists(filepath):
                    repo.index.add([filepath])

    if repo.is_dirty():
        if 'y' == input('Create commit (y/n)?'):
            utils.create_commit(repo,
                                '⚙️ Get PDFs manually',
                                saved_args,
                                manual_author=True)
    else:
        logging.info('Retrieve PDFs manually and copy the files to '
                     f'the {PDF_DIRECTORY}. Afterwards, use '
                     'review_template pdf-get-man')

    print()

    status.review_instructions()

    return bib_db
