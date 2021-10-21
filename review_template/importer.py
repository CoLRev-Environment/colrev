#! /usr/bin/env python
import itertools
import logging
import multiprocessing as mp
import os
import re
import shutil
from itertools import chain

import bibtexparser
import git
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

import docker
from review_template import grobid_client
from review_template import repo_setup
from review_template import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

JOURNAL_ABBREVIATIONS, JOURNAL_VARIATIONS, CONFERENCE_ABBREVIATIONS = \
    utils.retrieve_crowd_resources()


def get_imported_entry_links():

    imported_entry_links = []
    try:
        imported_entry_links = pd.read_csv('imported_entry_links.csv',
                                           header=None)
        imported_entry_links = \
            imported_entry_links[imported_entry_links.columns[0]].tolist()
    except pd.errors.EmptyDataError:
        # ok if no search results have been imported before
        if not os.path.exists(MAIN_REFERENCES):
            pass

    return imported_entry_links


def load_entries(filepath):

    imported_entry_links = get_imported_entry_links()

    search_db = load_search_results_file(filepath)

    if search_db is None:
        return []

    search_file = os.path.basename(filepath)
    entry_list = []
    for entry in search_db.entries:
        entry['entry_link'] = search_file + '/' + entry['ID']
        if entry['entry_link'] in imported_entry_links:
            continue

        entry.update(status='retrieved')
        entry_list.append(entry)

    return entry_list


def save_imported_entry_links(bib_database):
    imported_entry_links = [x['entry_link'].split(';')
                            for x in bib_database.entries
                            if 'entry_link' in x]
    imported_entry_links = list(itertools.chain(*imported_entry_links))

    with open('imported_entry_links.csv', 'a') as fd:
        for el in imported_entry_links:
            fd.write(el + '\n')

    return


def import_entry(entry):

    if 'retrieved' != entry['status']:
        return entry

    entry.update(status='imported')

    return entry


def load_all_entries():

    print('Loading search results')
    bib_database = utils.load_references_bib(True, initialize=True)
    save_imported_entry_links(bib_database)
    load_pool = mp.Pool(repo_setup.config['CPUS'])
    search_files = utils.get_search_files()
    if any('.pdf' in x for x in search_files):
        grobid_client.start_grobid()
    additional_records = load_pool.map(load_entries, search_files)
    load_pool.close()
    load_pool.join()
    additional_records = list(chain(bib_database.entries, *additional_records))

    if os.path.exists('imported_entry_links.csv'):
        os.remove('imported_entry_links.csv')
    print()
    return additional_records


def bibutils_convert(script, data):

    assert script in ['ris2xml', 'end2xml',
                      'endx2xml', 'isi2xml',
                      'med2xml', 'xml2bib']

    if 'xml2bib' == script:
        script = script + ' -b -w '

    if isinstance(data, str):
        data = data.encode()

    client = docker.APIClient()
    try:
        container = \
            client.create_container('bibutils', script, stdin_open=True)
    except docker.errors.ImageNotFound:
        print('Docker image not found')
        return ''
        pass

    sock = client.attach_socket(container,
                                params={'stdin': 1, 'stdout': 1,
                                        'stderr': 1, 'stream': 1})
    client.start(container)

    sock._sock.send(data)
    sock._sock.close()
    sock.close()

    client.wait(container)
    # status = client.wait(container)
    # status_code = status['StatusCode']
    stdout = client.logs(container, stderr=False).decode()
    # stderr = client.logs(container, stdout=False).decode()

    client.remove_container(container)

    # print('Exit: {}'.format(status_code))
    # print('log stdout: {}'.format(stdout))
    # print('log stderr: {}'.format(stderr))

    # TODO: else: raise error!

    return stdout


def getbib(file):
    with open(file) as bibtex_file:
        contents = bibtex_file.read()
        bib_r = re.compile(r'^@.*{.*,', re.M)
        if len(re.findall(bib_r, contents)) == 0:
            print('Error: Not a bib file? ' + os.path.basename(file))
            individual_bib_database = None
        else:
            with open(file) as bibtex_file:
                individual_bib_database = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=False,
                    common_strings=True,
                ).parse_file(bibtex_file, partial=True)
    return individual_bib_database


def ris2bib(file):
    with open(file) as reader:
        data = reader.read(4096)
    if 'TY  - ' not in data:
        print('Error: Not a ris file? ' + os.path.basename(file))
        return None

    with open(file) as reader:
        data = reader.read()

    data = bibutils_convert('ris2xml', data)
    data = bibutils_convert('xml2bib', data)
    db = bibtexparser.loads(data)
    return db


def end2bib(file):
    with open(file) as reader:
        data = reader.read(4096)
    if '%%T ' not in data:
        print('Error: Not an end file? ' + os.path.basename(file))
        return None

    with open(file) as reader:
        data = reader.read()

    data = bibutils_convert('end2xml', data)
    data = bibutils_convert('xml2bib', data)
    db = bibtexparser.loads(data)
    return db


def txt2bib(file):
    grobid_client.check_grobid_availability()
    with open(file) as f:
        references = [line.rstrip() for line in f]

    # Note: processCitationList currently not working!??!
    data = ''
    ind = 0
    for ref in references:
        options = {}
        options['consolidateCitations'] = '1'
        options['citations'] = ref
        r = requests.post(
            grobid_client.get_grobid_url() + '/api/processCitation',
            data=options,
            headers={'Accept': 'application/x-bibtex'}
        )
        ind += 1
        data = data + '\n' + r.text.replace('{-1,', '{' + str(ind) + ',')

    db = bibtexparser.loads(data)
    return db


def preprocess_entries(data):
    for x in data:
        # TODO: more sophisticated setting of ENTRYTYPE, ID is needed.
        # could also use simple numbers as IDs...
        x['ENTRYTYPE'] = 'article'
        if 'citation_key' in x.keys():
            x['ID'] = x.pop('citation_key')
        for k, v in x.items():
            x[k] = str(v)

    return data


def csv2bib(file):
    try:
        data = pd.read_csv(file)
    except pd.errors.ParserError:
        print('Error: Not a csv file? ' + os.path.basename(file))
        pass
        return None
    data.columns = data.columns.str.replace(' ', '_')
    data.columns = data.columns.str.replace('-', '_')
    data = data.to_dict('records')
    data = preprocess_entries(data)

    db = BibDatabase()
    db.entries = data
    return db


def xlsx2bib(file):
    try:
        data = pd.read_excel(file)
    except pd.errors.ParserError:
        print('Error: Not an xlsx file? ' + os.path.basename(file))
        pass
        return None
    data.columns = data.columns.str.replace(' ', '_')
    data.columns = data.columns.str.replace('-', '_')
    data = data.to_dict('records')
    data = preprocess_entries(data)

    db = BibDatabase()
    db.entries = data
    return db


def move_to_pdf_dir(filepath):
    # We should avoid re-extracting data from PDFs repeatedly (e.g., status.py)
    if not os.path.exists('/pdfs'):
        os.mkdir('/pdfs')
        shutil.move(filepath, '/pdfs/' + filepath)
    return


# curl -v --form input=@./profit.pdf localhost:8070/api/processHeaderDocument
# curl -v --form input=@./thefile.pdf -H "Accept: application/x-bibtex"
# -d "consolidateHeader=0" localhost:8070/api/processHeaderDocument
def pdf2bib(file):
    grobid_client.check_grobid_availability()

    # TODO: switch consolidateHeader on again once issue is resolved:
    # https://github.com/kermitt2/grobid/issues/837
    r = requests.post(
        grobid_client.get_grobid_url() + '/api/processHeaderDocument',
        headers={'Accept': 'application/x-bibtex'},
        params={'consolidateHeader': '0'},
        files=dict(input=open(file, 'rb'))
    )
    print(r.status_code)
    print(r.request.url)
    print(r.request.headers)
    # print(r.request.body)

    if 200 == r.status_code:
        print(r.text)
        print(file)
        db = bibtexparser.loads(r.text)
        with open(file, 'w') as f:
            f.write(r.text)
        move_to_pdf_dir(file.replace('.pdf', '.bib'))

        return db
    if 500 == r.status_code:
        print('Error: Not a readable pdf file? ' + os.path.basename(file))
        print(f'Grobid: {r.text}')
        return None

    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
    return None


def pdfRefs2bib(file):
    grobid_client.check_grobid_availability()

    r = requests.post(
        grobid_client.get_grobid_url() + '/api/processReferences',
        files=dict(input=open(file, 'rb')),
        data={'consolidateHeader': '0', 'consolidateCitations': '1'},
        headers={'Accept': 'application/x-bibtex'}
    )
    if 200 == r.status_code:
        db = bibtexparser.loads(r.text)
        move_to_pdf_dir(file.replace('.pdf', '.bib'))
        return db
    if 500 == r.status_code:
        print('Error: Not a readable pdf file? ' + os.path.basename(file))
        print(f'Grobid: {r.text}')
        return None

    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
    return None


def load_search_results_file(search_file_path):

    search_file = os.path.basename(search_file_path)

    importer_scripts = {'bib': getbib,
                        'ris': ris2bib,
                        'end': end2bib,
                        'txt': txt2bib,
                        'csv': csv2bib,
                        'xlsx': xlsx2bib,
                        'pdf': pdf2bib,
                        'pdf_refs': pdfRefs2bib}

    assert any(search_file.endswith(ext) for ext in importer_scripts.keys())

    # Note: after the search_result_file (non-bib formats) has been loaded
    # for the first time, a corresponding bib_file is saved, which allows
    # for more efficient status checking, tracing, validation
    # This also applies to the pipeline_validation_hooks and is particularly
    # relevant for pdf sources that require long processing times
    corresponding_bib_file = search_file[:search_file.rfind('.')] + '.bib'

    if os.path.exists(corresponding_bib_file) and \
            not '.bib' == search_file[-4]:
        return None

    filetype = search_file[search_file.rfind('.')+1:]
    if 'pdf' == filetype:
        if search_file.endswith('_ref_list.pdf'):
            filetype = 'pdf_refs'
    if filetype in importer_scripts.keys():
        print(f' - Loading {filetype}: {search_file}')
        db = importer_scripts[filetype](search_file_path)
        if db is None:
            return None
        if corresponding_bib_file != search_file and \
                not '.bib' == search_file[-4]:
            new_file_path = search_file_path.replace('.' + filetype, '.bib')
            with open(new_file_path, 'w') as fi:
                fi.write(bibtexparser.dumps(db))
        return db
    else:
        print('Filetype not recognized: ' + search_file)
        return None


def create_commit(r, bib_database):
    if bib_database is None:
        print('- No entries imported')
        return False

    if 0 == len(bib_database.entries):
        print('- No entries imported')
        return False

    r.index.add(utils.get_search_files())

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    if MAIN_REFERENCES not in [i.a_path for i in r.index.diff(None)] and \
            MAIN_REFERENCES not in r.untracked_files:
        print(' - No new records added to MAIN_REFERENCES')
        return False
    else:
        # to avoid failing pre-commit hooks
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        utils.save_bib_file(bib_database, MAIN_REFERENCES)

        r.index.add([MAIN_REFERENCES])
        hook_skipping = 'false'
        if not repo_setup.config['DEBUG_MODE']:
            hook_skipping = 'true'

        r.index.commit(
            '⚙️ Import search results ' + utils.get_version_flag() +
            utils.get_commit_report(),
            author=git.Actor('script:importer.py', ''),
            committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                                repo_setup.config['EMAIL']),
            skip_hooks=hook_skipping
        )
        return True
