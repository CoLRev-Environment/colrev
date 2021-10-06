#! /usr/bin/env python
import csv
from datetime import datetime
from time import gmtime
from time import strftime

import git
import pandas as pd
import requests
import tqdm
import yaml

from review_template import entry_hash_function
from review_template import grobid_client
from review_template import utils

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

SEARCH_DETAILS = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['SEARCH_DETAILS']

with open('private_config.yaml') as private_config_yaml:
    private_config = yaml.load(private_config_yaml, Loader=yaml.FullLoader)

EMAIL = private_config['params']['EMAIL']
GIT_ACTOR = private_config['params']['GIT_ACTOR']

data_dir = ''


def process_backward_search(pdf_filename, bib_filename):

    search_details = pd.read_csv(SEARCH_DETAILS)

    if bib_filename in search_details['source_url']:
        return

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

    if len(search_details.index) == 0:
        iteration_number = 1
    else:
        iteration_number = str(int(search_details['iteration'].max()))

    new_record = pd.DataFrame(
        [[
            bib_filename,
            r.text.count('\n@'),
            iteration_number,
            datetime.today().strftime('%Y-%m-%d'),
            datetime.today().strftime('%Y-%m-%d'),
            bib_filename,
            '',
            'backward_search.py',
            '',
        ]],
        columns=[
            'filename',
            'number_records',
            'iteration',
            'date_start',
            'date_completion',
            'source_url',
            'search_parameters',
            'responsible',
            'comment',
        ],
    )
    search_details = pd.concat([search_details, new_record])
    search_details.to_csv(
        SEARCH_DETAILS,
        index=False, quoting=csv.QUOTE_ALL,
    )

    return bib_filename


def create_commit(bibfilenames):

    r = git.Repo()

    r.index.add([SEARCH_DETAILS])
    for f in bibfilenames:
        r.index.add([f])

    flag, flag_details = utils.get_version_flags()

    r.index.commit(
        '⚙️ Backward search ' + flag + flag_details +
        '\n - Using backward_search.py' +
        '\n - ' + utils.get_package_details(),
        author=git.Actor('script:backward_search.py', ''),
        committer=git.Actor(GIT_ACTOR, EMAIL),
    )

    return


def main():

    print('Backward search')
    grobid_client.start_grobid()
    citation_keys = utils.get_included_papers()

    print(strftime('%Y-%m-%d %H:%M:%S', gmtime()))
    bibfilenames = []
    for citation_key in tqdm.tqdm(citation_keys):
        backward_search_path = data_dir + 'search/'
        bib_filename = backward_search_path + citation_key + '_bw_search.bib'
        pdf_filename = data_dir + 'pdfs/' + citation_key + '.pdf'
        bibfilename = process_backward_search(pdf_filename, bib_filename)
        bibfilenames.append(bibfilename)
    print(strftime('%Y-%m-%d %H:%M:%S', gmtime()))

    create_commit(bibfilenames)


if __name__ == '__main__':
    main()
