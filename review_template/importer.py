#! /usr/bin/env python
import csv
import itertools
import logging
import multiprocessing as mp
import os
from itertools import chain

import bibtexparser
import git
import yaml
from bibtexparser.customization import convert_to_unicode

import docker
from review_template import cleanse_records
from review_template import entry_hash_function
from review_template import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

with open('private_config.yaml') as private_config_yaml:
    private_config = yaml.load(private_config_yaml, Loader=yaml.FullLoader)

if 'CPUS' not in private_config['params']:
    CPUS = mp.cpu_count()-1
else:
    CPUS = private_config['params']['CPUS']

DEBUG_MODE = (1 == private_config['params']['DEBUG_MODE'])
GIT_ACTOR = private_config['params']['GIT_ACTOR']
EMAIL = private_config['params']['EMAIL']


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
                print('  dropped ' + val + ' field')
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
    with open('imported_entry_links.csv') as read_obj:
        csv_reader = csv.reader(read_obj)
        for row in csv_reader:
            imported_entry_links.append(row[0])
    return imported_entry_links


def load_entries(bib_file):

    imported_entry_links = get_imported_entry_links()

    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)
        search_file = os.path.basename(bib_file)
        entry_list = []
        for entry in individual_bib_database.entries:
            entry['entry_link'] = search_file + '/' + entry['ID']
            if entry['entry_link'] in imported_entry_links:
                continue

            # Note: we assume that the metadata of doi.org is complete.
            complete_based_on_doi = False
            if not is_sufficiently_complete(entry):
                entry = cleanse_records.get_doi_from_crossref(entry)
                if 'doi' in entry:
                    # try completion based on doi
                    doi_metadata = \
                        cleanse_records.retrieve_doi_metadata(entry.copy())
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
                entry = cleanse_records.correct_entrytypes(entry)

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

    print('Load additional records...')

    save_imported_entry_links(bib_database)

    # additional_records = load_entries(utils.get_bib_files()[0])
    pool = mp.Pool(processes=CPUS)
    additional_records = pool.map(load_entries, utils.get_bib_files())
    additional_records = list(chain(*additional_records))

    citation_key_list = [entry['ID'] for entry in bib_database.entries]
    for entry in additional_records:
        if 'not_imported' == entry['status'] or \
                'needs_manual_completion' == entry['status']:
            entry.update(ID=utils.generate_citation_key_blacklist(
                entry, citation_key_list,
                entry_in_bib_db=False,
                raise_error=False))
            citation_key_list.append(entry['ID'])

        if not 'needs_manual_completion' == entry['status']:
            entry = cleanse_records.homogenize_entry(entry)

            # Note: the cleanse_records.py will homogenize more cases because
            # it runs speculative_changes(entry)
            entry = cleanse_records.apply_local_rules(entry)
            entry = cleanse_records.apply_crowd_rules(entry)
            entry = drop_fields(entry)
            entry.update(status='imported')

    if os.path.exists('imported_entry_links.csv'):
        os.remove('imported_entry_links.csv')

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


def ris2bib(file):
    with open(file) as reader:
        data = reader.read()
    data = bibutils_convert('ris2xml', data)
    data = bibutils_convert('xml2bib', data)
    return data


def end2bib(file):
    with open(file) as reader:
        data = reader.read()
    data = bibutils_convert('end2xml', data)
    data = bibutils_convert('xml2bib', data)
    return data


def convert_non_bib_files(r):

    search_dir = os.path.join(os.getcwd(), 'search/')

    ris_files = [os.path.join(search_dir, x)
                 for x in os.listdir(search_dir) if x.endswith('.ris')]
    for ris_file in ris_files:
        corresponding_bib_file = ris_file.replace('.ris', '.bib')
        if os.path.exists(corresponding_bib_file):
            continue
        print('Converting ris file to bib: ' + os.path.basename(ris_file))
        data = ris2bib(ris_file)
        with open(corresponding_bib_file, 'w') as file:
            file.write(data)
            file.close()
        r.index.add([ris_file])

    end_files = [os.path.join(search_dir, x)
                 for x in os.listdir(search_dir) if x.endswith('.end')]
    for end_file in end_files:
        corresponding_bib_file = end_file.replace('.end', '.bib')
        if os.path.exists(corresponding_bib_file):
            continue
        print('Converting end file to bib: ' + os.path.basename(end_file))
        data = end2bib(end_file)
        with open(corresponding_bib_file, 'w') as file:
            file.write(data)
            file.close()
        r.index.add([end_file])

    return


def create_commit(r, bib_database):

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)] or \
            MAIN_REFERENCES in r.untracked_files:
        # to avoid failing pre-commit hooks
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        utils.save_bib_file(bib_database, MAIN_REFERENCES)

        r.index.add([MAIN_REFERENCES])
        r.index.add(utils.get_bib_files())
        hook_skipping = 'false'
        if not DEBUG_MODE:
            hook_skipping = 'true'

        flag, flag_details = utils.get_version_flags()

        r.index.commit(
            '⚙️ Import search results ' + flag + flag_details +
            '\n - ' + utils.get_package_details(),
            author=git.Actor('script:importer.py', ''),
            committer=git.Actor(GIT_ACTOR, EMAIL),
            skip_hooks=hook_skipping
        )
    else:
        print('- No new records added to MAIN_REFERENCES')
    return
