#! /usr/bin/env python
import csv
import json
import multiprocessing as mp
import os

import git
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase

from review_template import process
from review_template import repo_setup
from review_template import utils

pdfs_retrieved = 0
existing_pdfs_linked = 0

# https://github.com/ContentMine/getpapers


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
    global missing_entries

    if 'needs_retrieval' != entry.get('pdf_status', 'NA'):
        return entry

    PDF_DIRECTORY = repo_setup.paths['PDF_DIRECTORY']

    if not os.path.exists(PDF_DIRECTORY):
        os.mkdir(PDF_DIRECTORY)

    pdf_filepath = os.path.join(PDF_DIRECTORY, entry['ID'] + '.pdf')

    if os.path.exists(pdf_filepath):
        entry.update(pdf_status='needs_preparation')
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
                        entry.update('pdf_status', 'needs_preparation')
                        pdfs_retrieved += 1
                    else:
                        os.remove(pdf_filepath)
                else:
                    print(f'Unpaywall retrieval error {res.status_code}/{url}')

    if not os.path.exists(pdf_filepath):
        missing_entries.entries.append(entry)

    return entry


def acquire_pdfs(db, repo):

    print('Acquire PDFs')
    utils.require_clean_repo(repo, ignore_pattern='pdfs/')
    process.check_delay(db, min_status_requirement='processed')

    global pdfs_retrieved
    global existing_pdfs_linked
    global missing_entries
    missing_entries = BibDatabase()

    BATCH_SIZE = repo_setup.config['BATCH_SIZE']
    print('TODO: BATCH_SIZE')

    # for entry in db.entries:
    #     entry = acquire_pdf(entry)

    pool = mp.Pool(repo_setup.config['CPUS'])
    db.entries = pool.map(acquire_pdf, db.entries)
    pool.close()
    pool.join()

    if existing_pdfs_linked > 0:
        print(f' - {existing_pdfs_linked} existing PDFs linked in bib file')
    if pdfs_retrieved > 0:
        print(f' - {pdfs_retrieved} PDFs retrieved')
    else:
        print('  - No PDFs retrieved')

    if len(missing_entries.entries) > 0:
        missing_entries_df = pd.DataFrame.from_records(missing_entries.entries)
        col_order = [
            'ID', 'author', 'title', 'journal', 'booktitle',
            'year', 'volume', 'number', 'pages', 'doi'
        ]
        missing_entries_df = missing_entries_df.reindex(col_order, axis=1)
        missing_entries_df.to_csv('missing_pdf_files.csv',
                                  index=False, quoting=csv.QUOTE_ALL)

        print(f' - {len(missing_entries.entries)} PDFs missing '
              '(see missing_pdf_files.csv)')

    create_commit(repo, db)

    return db


def create_commit(repo, db):

    MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

    utils.save_bib_file(db, MAIN_REFERENCES)

    if 'GIT' == repo_setup.config['PDF_HANDLING']:
        dirname = repo_setup.paths['PDF_DIRECTORY']
        for filepath in os.listdir(dirname):
            if filepath.endswith('.pdf'):
                repo.index.add([os.path.join(dirname, filepath)])

    hook_skipping = 'false'
    if not repo_setup.config['DEBUG_MODE']:
        hook_skipping = 'true'

    if MAIN_REFERENCES not in [i.a_path for i in repo.index.diff(None)] and \
            MAIN_REFERENCES not in [i.a_path for i in repo.head.commit.diff()]:
        print(' - No new records changed in MAIN_REFERENCES')
        return False
    else:
        repo.index.add([MAIN_REFERENCES])
        repo.index.commit(
            '⚙️ Acquire PDFs ' + utils.get_version_flag() +
            utils.get_commit_report(),
            author=git.Actor('script:pdfs.py', ''),
            committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                                repo_setup.config['EMAIL']),
            skip_hooks=hook_skipping
        )
        return True


def main():

    acquire_pdfs()


if __name__ == '__main__':
    main()
