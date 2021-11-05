#! /usr/bin/env python
import csv
import json
import logging
import multiprocessing as mp
import os

import click
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


def retrieve_pdf(record):
    global pdfs_retrieved
    global existing_pdfs_linked

    if 'needs_retrieval' != record.get('pdf_status', 'NA'):
        return record

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return record
        else:
            current_batch_counter.value += 1

    PDF_DIRECTORY = repo_setup.paths['PDF_DIRECTORY']

    if not os.path.exists(PDF_DIRECTORY):
        os.mkdir(PDF_DIRECTORY)

    pdf_filepath = os.path.join(PDF_DIRECTORY, record['ID'] + '.pdf')

    if os.path.exists(pdf_filepath):
        record.update(pdf_status='imported')
        if 'file' not in record:
            record.update(file=':' + pdf_filepath + ':PDF')
            logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                         'linked pdf')
            existing_pdfs_linked += 1
        return record

    if 'doi' in record:
        url = unpaywall(record['doi'])
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
                        record.update(file=':' + pdf_filepath + ':PDF')
                        record.update(pdf_status='imported')
                        pdfs_retrieved += 1
                    else:
                        os.remove(pdf_filepath)
                else:
                    logging.info('Unpaywall retrieval error '
                                 f'{res.status_code}/{url}')
    return record


def get_missing_records(bib_db):
    missing_records = BibDatabase()
    for record in bib_db.entries:
        if 'needs_retrieval' == record.get('pdf_status', 'NA'):
            missing_records.entries.append(record)
    return missing_records


def print_details(missing_records):
    global pdfs_retrieved
    global existing_pdfs_linked

    if existing_pdfs_linked > 0:
        logging.info(
            f'{existing_pdfs_linked} existing PDFs linked in bib file')
    if pdfs_retrieved > 0:
        logging.info(f'{pdfs_retrieved} PDFs retrieved')
    else:
        logging.info('No PDFs retrieved')
    if len(missing_records.entries) > 0:
        logging.info(f'{len(missing_records.entries)} PDFs missing ')
    return


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

        logging.info('See missing_pdf_files.csv for paper details')
    return


def main(bib_db, repo):

    utils.require_clean_repo(repo, ignore_pattern='pdfs/')
    process.check_delay(bib_db, min_status_requirement='pdf_needs_retrieval')
    global PAD
    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)

    print('TODO: download if there is a fulltext link in the record')

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
        bib_db.entries = pool.map(retrieve_pdf, bib_db.entries)
        pool.close()
        pool.join()

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        missing_records = get_missing_records(bib_db)

        if batch_end > 0:
            logging.info('Completed pdf retrieval batch '
                         f'(records {batch_start} to {batch_end})')

            print_details(missing_records)

            MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
            utils.save_bib_file(bib_db, MAIN_REFERENCES)
            repo.index.add([MAIN_REFERENCES])

            if 'GIT' == repo_setup.config['PDF_HANDLING']:
                dirname = repo_setup.paths['PDF_DIRECTORY']
                if os.path.exists(dirname):
                    for filepath in os.listdir(dirname):
                        if filepath.endswith('.pdf'):
                            repo.index.add([os.path.join(dirname, filepath)])

            in_process = utils.create_commit(repo, '⚙️ Retrieve PDFs')

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logging.info('No additional pdfs to retrieve')
            break

    export_retrieval_table(missing_records)
    print()

    status.review_instructions()

    return bib_db


@click.command()
def cli():
    # TODO: the global counters need to be adapted to multiprocessing

    bib_db = utils.load_main_refs()
    repo = init.get_repo()
    main(bib_db, repo)

    return 0


if __name__ == '__main__':
    bib_db = utils.load_main_refs()
    repo = init.get_repo()
    main(bib_db, repo)
