#! /usr/bin/env python
import configparser
import csv
import json
import os

import git
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase

from review_template import entry_hash_function
from review_template import utils
# from pdfminer.high_level import extract_text

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']
PDF_DIRECTORY = entry_hash_function.paths[HASH_ID_FUNCTION]['PDF_DIRECTORY']
SCREEN_FILE = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


pdfs_retrieved = 0
existing_pdfs_linked = 0
pdfs_available = 0

# https://github.com/ContentMine/getpapers


def unpaywall(doi, retry=0, pdfonly=True):

    r = requests.get(
        'https://api.unpaywall.org/v2/{doi}',
        params={'email': config['general']['EMAIL']},
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
    global pdfs_available
    global missing_entries

    print('TODO: check required status (join screening/needs pdf before)')
    # Note: this should replace the line
    # entry['ID'] in papers_to_acquire

    if not os.path.exists(PDF_DIRECTORY):
        os.mkdir(PDF_DIRECTORY)

    pdf_filepath = os.path.join(PDF_DIRECTORY, entry['ID'] + '.pdf')

    if os.path.exists(pdf_filepath):
        pdfs_available += 1
        if 'file' not in entry:
            entry.update(file=':' + pdf_filepath + ':PDF')
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
                        print(f'Retrieved pdf (unpaywall): {pdf_filepath}')
                        entry.update(file=':' + pdf_filepath + ':PDF')
                        pdfs_retrieved += 1
                    else:
                        os.remove(pdf_filepath)
                else:
                    print(f'Unpaywall retrieval error {res.status_code}/{url}')

    if not os.path.exists(pdf_filepath):
        missing_entries.entries.append(entry)

    return entry


def main():

    r = git.Repo('')
    utils.require_clean_repo(r)

    global pdfs_retrieved
    global existing_pdfs_linked
    global pdfs_available
    global missing_entries
    missing_entries = BibDatabase()

    print('Acquire PDFs')

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    assert os.path.exists(SCREEN_FILE)
    screen = pd.read_csv(SCREEN_FILE, dtype=str)

    papers_to_acquire = \
        screen.loc[screen.inclusion_2.notnull(), 'citation_key', ].tolist()

    for entry in bib_database.entries:
        if entry['ID'] in papers_to_acquire:
            entry = acquire_pdf(entry)

    print(f' - {len(papers_to_acquire)} pdfs required')
    print(f' - {pdfs_available} pdfs available')
    if existing_pdfs_linked > 0:
        print(f' - {existing_pdfs_linked} existing pdfs linked in bib file')
    print(f' - {pdfs_retrieved} pdfs retrieved')

    if len(missing_entries.entries) > 0:
        missing_entries_df = pd.DataFrame.from_records(missing_entries.entries)
        col_order = [
            'ID', 'author', 'title', 'journal', 'booktitle',
            'year', 'volume', 'number', 'pages', 'doi'
        ]
        missing_entries_df = missing_entries_df.reindex(col_order, axis=1)
        missing_entries_df.to_csv('missing_pdf_files.csv',
                                  index=False, quoting=csv.QUOTE_ALL)

        print(f' - {len(missing_entries.entries)} pdfs missing '
              '(see missing_pdf_files.csv)')

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    # TODO: create commit


if __name__ == '__main__':
    main()
