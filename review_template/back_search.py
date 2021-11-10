#! /usr/bin/env python
import logging
import os
from datetime import datetime

import bibtexparser
import git
import requests

from review_template import grobid_client
from review_template import repo_setup
from review_template import utils

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
SEARCH_DETAILS = repo_setup.paths['SEARCH_DETAILS']
BATCH_SIZE = repo_setup.config['BATCH_SIZE']

data_dir = ''


def backward_search(record: dict) -> dict:

    if record['pdf_status'] != 'prepared':
        return record

    PDF_DIRECTORY = repo_setup.paths['PDF_DIRECTORY']

    curdate = datetime.today().strftime('%Y-%m-%d')
    bib_filename = \
        os.path.join(
            data_dir, f'search/{curdate}-{record["ID"]}_bw_search.bib')
    pdf_filename = os.path.join(data_dir, PDF_DIRECTORY, f'{record["ID"]}.pdf')

    filename = record.get('file', 'NA').replace('.pdf:PDF', '.pdf')\
        .replace(':', '')
    pdf_path = os.path.join(os.getcwd(), filename)
    if not os.path.exists(pdf_path):
        logging.error(f'File does not exist ({record["ID"]})')
        return record

    search_details = utils.load_search_details()

    if bib_filename in [x['source_url'] for x in search_details]:
        return record

    # alternative python-batch:
    # https://github.com/kermitt2/grobid_client_python
    grobid_client.check_grobid_availability()

    options = {'consolidateHeader': '0', 'consolidateCitations': '1'}
    r = requests.post(
        grobid_client.get_grobid_url() + '/api/processReferences',
        files=dict(input=open(pdf_filename, 'rb')),
        data=options,
        headers={'Accept': 'application/x-bibtex'}
    )

    bib_content = r.text.encode('utf-8')
    with open(bib_filename, 'wb') as f:
        f.write(bib_content)
        record['bib_filename'] = bib_filename

    bib_db = bibtexparser.loads(bib_content)
    logging.info(f'backward_search({record["ID"]}):'
                 f' {len(bib_db.entries)} records')

    new_record = {'filename': bib_filename,
                  'search_type': 'BACK_CIT',
                  'source_name': 'PDF',
                  'source_url': bib_filename.replace('search/', ''),
                  'search_parameters': 'NA',
                  'comment': 'extracted with review_template back-search',
                  }

    search_details.append(new_record)

    utils.save_search_details(search_details)

    return record


def main() -> None:
    saved_args = locals()
    repo = git.Repo()
    utils.require_clean_repo(repo)
    utils.reset_log()
    logging.info('Backward search')
    grobid_client.start_grobid()
    bib_db = utils.load_main_refs()

    for record in bib_db.entries:
        backward_search(record)

    bibfilenames = [x['bib_filename']
                    for x in bib_db.entries if 'bib_filename' in x]
    if len(bibfilenames) > 0:
        repo.index.add([SEARCH_DETAILS])
        for f in bibfilenames:
            repo.index.add([f])
        utils.create_commit(repo, '⚙️ Backward search', saved_args)

    return
