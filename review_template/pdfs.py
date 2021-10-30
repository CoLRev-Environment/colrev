#! /usr/bin/env python
import csv
import json
import logging
import multiprocessing as mp
import os

import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase

from review_template import init
from review_template import process
from review_template import repo_setup
from review_template import status
from review_template import utils

pdfs_retrieved = 0
existing_pdfs_linked = 0

# https://github.com/ContentMine/getpapers

BATCH_SIZE = repo_setup.config['BATCH_SIZE']

current_batch_counter = mp.Value('i', 0)


def unpaywall(doi, retry=0, pdfonly=True):

    r = requests.get(
        'https://api.unpaywall.org/v2/{doi}',
        params={'email': repo_setup.config['EMAIL']},
    )

    if r.status_code == 404:
        # print("Invalid/unknown DOI {}".format(doi))
        return None

    if r.status_code == 500:
        # print("Unpaywall API failed. Try: {}/3".format(retry+1))

        if retry < 3:
            return unpaywall(doi, retry+1)
        else:
            # print("Retried 3 times and failed. Giving up")
            return None

    best_loc = None
    try:
        best_loc = r.json()['best_oa_location']
    except json.decoder.JSONDecodeError:
        # print("Response was not json")
        # print(r.text)
        return None
    except KeyError:
        # print("best_oa_location not set")
        # print(r.text)
        return None
    # except:
        # print("Something weird happened")
        # print(r.text)
        #  return None

    if not r.json()['is_oa'] or best_loc is None:
        # print("No OA paper found for {}".format(doi))
        return None

    if(best_loc['url_for_pdf'] is None and pdfonly is True):
        # print("No PDF found..")
        # print(best_loc)
        return None
    else:
        return best_loc['url']

    return best_loc['url_for_pdf']


def is_pdf(path_to_file):

    # TODO: add exceptions
    # try:
    # extract_text(path_to_file)
    return True
    # except:
    #    return False


def acquire_pdf(entry):
    global pdfs_retrieved
    global existing_pdfs_linked

    if 'needs_retrieval' != entry.get('pdf_status', 'NA'):
        return entry

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return entry
        else:
            current_batch_counter.value += 1

    PDF_DIRECTORY = repo_setup.paths['PDF_DIRECTORY']

    if not os.path.exists(PDF_DIRECTORY):
        os.mkdir(PDF_DIRECTORY)

    pdf_filepath = os.path.join(PDF_DIRECTORY, entry['ID'] + '.pdf')

    if os.path.exists(pdf_filepath):
        entry.update(pdf_status='imported')
        if 'file' not in entry:
            entry.update(file=':' + pdf_filepath + ':PDF')
            logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                         'linked pdf')
            existing_pdfs_linked += 1
        return entry

    if 'doi' in entry:
        url = unpaywall(entry['doi'])
        if url is not None:
            if 'Invalid/unknown DOI' not in url:
                res = requests.get(
                    url, headers={
                        'User-Agent': 'Chrome/51.0.2704.103',
                        'referer': 'https://www.doi.org',
                    },
                )
                if 200 == res.status_code:
                    with open(pdf_filepath, 'wb') as f:
                        f.write(res.content)
                    if is_pdf(pdf_filepath):
                        logging.info('Retrieved pdf (unpaywall):'
                                     f' {pdf_filepath}')
                        entry.update(file=':' + pdf_filepath + ':PDF')
                        entry.update(pdf_status='imported')
                        pdfs_retrieved += 1
                    else:
                        os.remove(pdf_filepath)
                else:
                    logging.info('Unpaywall retrieval error '
                                 f'{res.status_code}/{url}')
    return entry


def get_missing_entries(db):
    missing_entries = BibDatabase()
    for entry in db.entries:
        if 'needs_retrieval' == entry.get('pdf_status', 'NA'):
            missing_entries.entries.append(entry)
    return missing_entries


def print_details(missing_entries):
    global pdfs_retrieved
    global existing_pdfs_linked

    if existing_pdfs_linked > 0:
        logging.info(
            f'{existing_pdfs_linked} existing PDFs linked in bib file')
    if pdfs_retrieved > 0:
        logging.info(f'{pdfs_retrieved} PDFs retrieved')
    else:
        logging.info('No PDFs retrieved')
    if len(missing_entries.entries) > 0:
        logging.info(f'{len(missing_entries.entries)} PDFs missing ')
    return


def export_retrieval_table(missing_entries):

    if len(missing_entries.entries) > 0:
        missing_entries_df = pd.DataFrame.from_records(missing_entries.entries)
        col_order = [
            'ID', 'author', 'title', 'journal', 'booktitle',
            'year', 'volume', 'number', 'pages', 'doi'
        ]
        missing_entries_df = missing_entries_df.reindex(col_order, axis=1)
        missing_entries_df.to_csv('missing_pdf_files.csv',
                                  index=False, quoting=csv.QUOTE_ALL)

        logging.info('See missing_pdf_files.csv for paper details')
    return


def acquire_pdfs(db, repo):

    utils.require_clean_repo(repo, ignore_pattern='pdfs/')
    process.check_delay(db, min_status_requirement='pdf_needs_retrieval')

    print('TODO: download if there is a fulltext link in the entry')

    utils.reset_log()
    logging.info('Retrieve PDFs')

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logging.info('Continuing batch preparation started earlier')

        pool = mp.Pool(repo_setup.config['CPUS'])
        db.entries = pool.map(acquire_pdf, db.entries)
        pool.close()
        pool.join()

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        missing_entries = get_missing_entries(db)

        if batch_end > 0:
            logging.info('Completed pdf acquisition batch '
                         f'(entries {batch_start} to {batch_end})')

            print_details(missing_entries)

            MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
            utils.save_bib_file(db, MAIN_REFERENCES)
            repo.index.add([MAIN_REFERENCES])

            if 'GIT' == repo_setup.config['PDF_HANDLING']:
                dirname = repo_setup.paths['PDF_DIRECTORY']
                if os.path.exists(dirname):
                    for filepath in os.listdir(dirname):
                        if filepath.endswith('.pdf'):
                            repo.index.add([os.path.join(dirname, filepath)])

            in_process = utils.create_commit(repo, '⚙️ Acquire PDFs')

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logging.info('No additional pdfs to retrieve')
            break

    export_retrieval_table(missing_entries)
    print()
    return db


def main():

    db = utils.load_references_bib(True, initialize=True)
    repo = init.get_repo()
    acquire_pdfs(db, repo)

    status.review_instructions()
    return


if __name__ == '__main__':
    main()
