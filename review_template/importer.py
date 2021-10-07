#! /usr/bin/env python
import configparser
import itertools
import logging
import multiprocessing as mp
import os
import re
from itertools import chain

import bibtexparser
import git
import pandas as pd
import requests
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import docker
from review_template import entry_hash_function
from review_template import grobid_client
from review_template import prepare
from review_template import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']


MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']

JOURNAL_ABBREVIATIONS, JOURNAL_VARIATIONS, CONFERENCE_ABBREVIATIONS = \
    utils.retrieve_crowd_resources()

fields_to_keep = [
    'ID', 'hash_id', 'ENTRYTYPE',
    'author', 'year', 'title',
    'journal', 'booktitle', 'series',
    'volume', 'number', 'pages', 'doi',
    'abstract',
    'editor', 'book-group-author',
    'book-author', 'keywords', 'file',
    'status', 'fulltext', 'entry_link'
]
fields_to_drop = [
    'type', 'url', 'organization',
    'issn', 'isbn', 'note', 'issue',
    'unique-id', 'month', 'researcherid-numbers',
    'orcid-numbers', 'eissn', 'article-number',
    'publisher', 'author_keywords', 'source',
    'affiliation', 'document_type', 'art_number',
    'address', 'language', 'doc-delivery-number',
    'da', 'usage-count-last-180-days', 'usage-count-since-2013',
    'doc-delivery-number', 'research-areas',
    'web-of-science-categories', 'number-of-cited-references',
    'times-cited', 'journal-iso', 'oa', 'keywords-plus',
    'funding-text', 'funding-acknowledgement', 'day',
    'related', 'bibsource', 'timestamp', 'biburl'
]


def drop_fields(entry):
    for val in list(entry):
        if(val not in fields_to_keep):
            # drop all fields not in fields_to_keep
            entry.pop(val)
            # warn if fields are dropped that are not in fields_to_drop
            if val not in fields_to_drop:
                print(f'  dropped {val} field')
    return entry


def is_sufficiently_complete(entry):
    sufficiently_complete = False

    if 'article' == entry['ENTRYTYPE']:
        if all(x in entry
               for x in ['title', 'author', 'year', 'journal', 'volume']):
            if 'issue' in entry or 'number' in entry:
                sufficiently_complete = True
    elif 'inproceedings' == entry['ENTRYTYPE']:
        if all(x in entry for x in ['title', 'author', 'booktitle', 'year']):
            sufficiently_complete = True
    elif 'book' == entry['ENTRYTYPE']:
        if all(x in entry for x in ['title', 'author', 'year']):
            sufficiently_complete = True

    return sufficiently_complete


def get_imported_entry_links():

    imported_entry_links = []

    imported_entry_links = pd.read_csv('imported_entry_links.csv', header=None)
    imported_entry_links = \
        imported_entry_links[imported_entry_links.columns[0]].tolist()

    return imported_entry_links


def load_entries(filepath):

    imported_entry_links = get_imported_entry_links()

    individual_bib_database = load_search_results_file(filepath)

    if individual_bib_database is None:
        return []

    search_file = os.path.basename(filepath)
    entry_list = []
    for entry in individual_bib_database.entries:
        entry['entry_link'] = search_file + '/' + entry['ID']
        if entry['entry_link'] in imported_entry_links:
            continue

        # Note: we assume that the metadata of doi.org is complete.
        complete_based_on_doi = False
        if not is_sufficiently_complete(entry):
            entry = prepare.get_doi_from_crossref(entry)
            if 'doi' in entry:
                # try completion based on doi
                doi_metadata = \
                    prepare.retrieve_doi_metadata(entry.copy())
                for key, value in doi_metadata.items():
                    if key not in entry.keys() and key in ['author',
                                                           'year',
                                                           'title',
                                                           'journal',
                                                           'booktitle',
                                                           'number',
                                                           'volume',
                                                           'issue',
                                                           'pages']:
                        entry[key] = value
                complete_based_on_doi = True

            # fix type-mismatches
            # e.g., conference paper with ENTRYTYPE=article
            entry = prepare.correct_entrytypes(entry)

        if is_sufficiently_complete(entry) or complete_based_on_doi:
            hid = entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)
            entry.update(hash_id=hid)
            entry.update(status='not_imported')
        else:
            entry.update(status='needs_manual_completion')

        entry_list.append(entry)

    return entry_list


def save_imported_hash_ids(bib_database):

    imported_hash_ids = [entry['hash_id'].split(',') for
                         entry in bib_database.entries
                         if not 'needs_manual_completion' == entry['status']]
    imported_hash_ids = list(itertools.chain(*imported_hash_ids))

    with open('imported_hash_ids.csv', 'a') as fd:
        for p_hid in imported_hash_ids:
            fd.write(p_hid + '\n')

    return


def save_imported_entry_links(bib_database):
    imported_entry_links = [x['entry_link'].split(';')
                            for x in bib_database.entries
                            if 'entry_link' in x]
    imported_entry_links = list(itertools.chain(*imported_entry_links))

    with open('imported_entry_links.csv', 'a') as fd:
        for el in imported_entry_links:
            fd.write(el + '\n')

    return


def load(bib_database):

    print('Loading search results')

    save_imported_entry_links(bib_database)

    # additional_records = load_entries(utils.get_bib_files()[0])
    pool = mp.Pool(config.getint('general', 'CPUS', fallback=mp.cpu_count()-1))

    bib_non_processed = [x for x in bib_database.entries
                         if x.get('status', 'NA') != 'processed']

    additional_records = pool.map(load_entries, utils.get_search_files())
    additional_records = list(chain(bib_non_processed, *additional_records))

    citation_key_list = [entry['ID'] for entry in bib_database.entries]
    for entry in additional_records:
        if 'prepared' == entry['status'] or \
                'needs_manual_merging' == entry['status']:
            continue
        if 'not_imported' == entry['status'] or \
                'needs_manual_completion' == entry['status']:
            entry.update(ID=utils.generate_citation_key_blacklist(
                entry, citation_key_list,
                entry_in_bib_db=False,
                raise_error=False))
            citation_key_list.append(entry['ID'])

        if not 'needs_manual_completion' == entry['status']:
            entry = prepare.homogenize_entry(entry)

            # Note: the prepare.py will homogenize more cases because
            # it runs speculative_changes(entry)
            entry = prepare.apply_local_rules(entry)
            entry = prepare.apply_crowd_rules(entry)
            entry = drop_fields(entry)
            entry.update(status='imported')

    if os.path.exists('imported_entry_links.csv'):
        os.remove('imported_entry_links.csv')

    r = git.Repo()
    r.index.add(utils.get_search_files())

    return additional_records


def bibutils_convert(script, data):

    assert script in ['ris2xml', 'end2xml',
                      'endx2xml', 'isi2xml', 'med2xml', 'xml2bib']

    if 'xml2bib' == script:
        script = script + ' -b -w '

    if isinstance(data, str):
        data = data.encode()

    client = docker.APIClient()
    try:

        container = client.create_container(
            'bibutils',
            script,
            stdin_open=True,
        )
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
                individual_bib_database = bibtexparser.bparser.BibTexParser(
                    customization=convert_to_unicode, common_strings=True,
                ).parse_file(bibtex_file, partial=True)
    return individual_bib_database


def ris2bib(file):
    with open(file) as reader:
        data = reader.read()
    if 'TY  - ' not in data:
        print('Error: Not a ris file? ' + os.path.basename(file))
        return None

    data = bibutils_convert('ris2xml', data)
    data = bibutils_convert('xml2bib', data)
    db = bibtexparser.loads(data)
    return db


def end2bib(file):
    with open(file) as reader:
        data = reader.read()
    if '%%T ' not in data:
        print('Error: Not an end file? ' + os.path.basename(file))
        return None

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
            # if ' ' in k:
            #     x[k.replace(' ', '_')] = x.pop(k)

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


def pdf2bib(file):
    grobid_client.check_grobid_availability()

    options = {'consolidateHeader': '1'}
    r = requests.put(
        grobid_client.get_grobid_url() + '/api/processHeaderDocument',
        files=dict(input=open(file, 'rb')),
        params=options,
        headers={'Accept': 'application/x-bibtex'}
    )
    if 200 == r.status_code:
        db = bibtexparser.loads(r.text)
        return db
    if 500 == r.status_code:
        print('Error: Not a readable pdf file? ' + os.path.basename(file))
        print(f'Grobid: {r.text}')
        return None

    # print(r.request.url)
    # print(r.request.body)
    # print(r.request.headers)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
    return None


def pdfRefs2bib(file):
    grobid_client.check_grobid_availability()

    options = {'consolidateHeader': '0', 'consolidateCitations': '1'}
    r = requests.post(
        grobid_client.get_grobid_url() + '/api/processReferences',
        files=dict(input=open(file, 'rb')),
        data=options,
        headers={'Accept': 'application/x-bibtex'}
    )
    if 200 == r.status_code:
        db = bibtexparser.loads(r.text)
        return db
    if 500 == r.status_code:
        print('Error: Not a readable pdf file? ' + os.path.basename(file))
        print(f'Grobid: {r.text}')
        return None

    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
    return None


def load_search_results_file(search_file):

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
    corresponding_bib_file = search_file[search_file.rfind('.'):] + '.bib'
    if os.path.exists(corresponding_bib_file):
        return None

    filetype = search_file[search_file.rfind('.')+1:]
    if 'pdf' == filetype:
        if search_file.endswith('_ref_list.pdf'):
            filetype = 'pdf_refs'
    if filetype in importer_scripts.keys():
        print(f'- Loading {filetype}: {os.path.basename(search_file)}')
        db = importer_scripts[filetype](search_file)
        if db is None:
            return None
        if corresponding_bib_file != search_file:
            with open(search_file.replace(filetype, '.bib'), 'w') as file:
                file.write(bibtexparser.dumps(db))
                file.close()
        return db
    else:
        print('Filetype not recognized: ' + os.path.basename(search_file))
        return None


def create_commit(r, bib_database):
    if bib_database is None:
        print('- No entries imported')
        return False

    if 0 == len(bib_database.entries):
        print('- No entries imported')
        return False

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    if MAIN_REFERENCES not in [i.a_path for i in r.index.diff(None)] and \
            MAIN_REFERENCES not in r.untracked_files:
        print('- No new records added to MAIN_REFERENCES')
        return False
    else:
        # to avoid failing pre-commit hooks
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        utils.save_bib_file(bib_database, MAIN_REFERENCES)

        r.index.add([MAIN_REFERENCES])
        hook_skipping = 'false'
        if not config.getboolean('general', 'DEBUG_MODE'):
            hook_skipping = 'true'

        flag, flag_details = utils.get_version_flags()

        r.index.commit(
            '⚙️ Import search results ' + flag + flag_details +
            '\n - ' + utils.get_package_details(),
            author=git.Actor('script:importer.py', ''),
            committer=git.Actor(config['general']['GIT_ACTOR'],
                                config['general']['EMAIL']),
            skip_hooks=hook_skipping
        )
        return True
