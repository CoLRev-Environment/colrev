#! /usr/bin/env python
import json
import logging
import os
from datetime import datetime

import git
import pandas as pd
import requests
import yaml
from yaml import safe_load

from review_template import grobid_client
from review_template import repo_setup
from review_template import utils

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
SEARCH_DETAILS = repo_setup.paths['SEARCH_DETAILS']
BATCH_SIZE = repo_setup.config['BATCH_SIZE']

data_dir = ''


def process_backward_search(record):

    if record['pdf_status'] != 'prepared':
        return record

    bib_filename = data_dir + 'search/' + record['ID'] + '_bw_search.bib'
    pdf_filename = data_dir + 'pdfs/' + record['ID'] + '.pdf'

    filename = record.get('file', 'NA').replace('.pdf:PDF', '.pdf')\
        .replace(':', '')
    pdf_path = os.path.join(os.getcwd(), filename)
    if not os.path.exists(pdf_path):
        logging.error(f'File does not exist ({record["ID"]})')
        return record

    with open(SEARCH_DETAILS) as f:
        search_details_df = pd.json_normalize(safe_load(f))
        search_details = search_details_df.to_dict('records')

    if bib_filename in [x['source_url'] for x in search_details]:
        return record

    logging.info(f'Extract references for {record["ID"]}')
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

    iteration = max(x['iteration'] for x in search_details)

    new_record = {'filename': bib_filename,
                  'search_type': 'BACK_CIT',
                  'source_name': 'PDF',
                  'source_url': bib_filename,
                  'iteration': int(iteration),
                  'start_date': datetime.today().strftime('%Y-%m-%d'),
                  'completion_date': datetime.today().strftime('%Y-%m-%d'),
                  'number_records': r.text.count('\n@'),
                  'search_parameters': 'NA',
                  'comment': 'backward_search.py',
                  }

    search_details.append(new_record)

    search_details_df = pd.DataFrame(search_details)
    orderedCols = ['filename', 'number_records', 'search_type',
                   'source_name', 'source_url', 'iteration',
                   'start_date', 'completion_date',
                   'search_parameters', 'comment']
    search_details_df = search_details_df.reindex(columns=orderedCols)

    with open(SEARCH_DETAILS, 'w') as f:
        yaml.dump(json.loads(search_details_df.to_json(orient='records')),
                  f, default_flow_style=False, sort_keys=False)

    return record


def main():
    repo = git.Repo()
    utils.require_clean_repo(repo)
    grobid_client.start_grobid()

    utils.reset_log()
    logging.info('Backward search')

    bib_db = utils.load_main_refs()

    for record in bib_db.entries:
        process_backward_search(record)

    bibfilenames = [x['bib_filename']
                    for x in bib_db.entries if 'bib_filename' in x]
    if len(bibfilenames) > 0:
        repo.index.add([SEARCH_DETAILS])
        for f in bibfilenames:
            repo.index.add([f])
        utils.create_commit(repo, '⚙️ Backward search')

    return


if __name__ == '__main__':
    main()
