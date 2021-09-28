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
    'source_file_path', 'source_id',
    'status', 'fulltext'
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
    'related'
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


def get_db_with_completion_edits(bib_file):
    completion_edits = []
    if os.path.exists('search/completion_edits.csv'):
        with open('search/completion_edits.csv') as read_obj:
            csv_reader = csv.DictReader(read_obj)
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    line_count += 1
                completion_edits.append([row['source_file_path'],
                                         row['source_id'],
                                         row['key'],
                                         row['value']])

    with open(bib_file) as bibtex_file:
        db = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        for entry in db.entries:
            entry.update(source_file_path=os.path.basename(bib_file))
            for completion_edit in completion_edits:
                if completion_edit[0] == entry['source_file_path'] and \
                        completion_edit[1] == entry['ID']:
                    entry[completion_edit[2]] = completion_edit[3]

    return db


def get_imported_hash_ids():
    imported_hash_ids = []
    with open('imported_hash_ids.csv') as read_obj:
        csv_reader = csv.reader(read_obj)
        for row in csv_reader:
            imported_hash_ids.append(row[0])
    return imported_hash_ids


def save_new_completion_edits(new_completion_edits):
    if [] == new_completion_edits:
        return

    if not os.path.exists('search/completion_edits.csv'):
        with open('search/completion_edits.csv', 'w') as wr_obj:
            writer = csv.writer(wr_obj, quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writerow(['source_file_path', 'source_id', 'key', 'value'])

    with open('search/completion_edits.csv', 'a') as wr_obj:
        writer = csv.writer(wr_obj, quotechar='"', quoting=csv.QUOTE_ALL)
        for completion_edit in new_completion_edits:
            writer.writerow(completion_edit)
    return


def load_entries(bib_file):

    imported_hash_ids = get_imported_hash_ids()
    individual_bib_database = get_db_with_completion_edits(bib_file)
    entry_list, new_completion_edits = [], []
    for entry in individual_bib_database.entries:
        # IMPORTANT NOTE: any modifications completed before this step
        # need to be considered when backward-tracing!
        # Tradeoff: preprocessing can help to reduce the number of
        # representations (hash_ids) for each record
        # but it also introduces complexity (backward tracing)

        if not is_sufficiently_complete(entry) and 'doi' in entry:
            # try completion based on doi (store in completion_edits file)
            entry = cleanse_records.get_doi_from_crossref(entry)
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
                    new_completion_edits.append([entry['source_file_path'],
                                                 entry['ID'],
                                                 key,
                                                 value])
            # fix type-mismatches
            # e.g., conference paper with ENTRYTYPE=article
            entry = cleanse_records.correct_entrytypes(entry)

        if is_sufficiently_complete(entry):
            hid = entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)
            entry.update(hash_id=hid)
            if entry['hash_id'] not in imported_hash_ids:
                entry.update(status='not_imported')
                entry_list.append(entry)
        else:
            entry.update(status='needs_manual_completion')
            entry.update(source_id=entry['ID'])
            entry_list.append(entry)

    save_new_completion_edits(new_completion_edits)

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


def load_additional_records(bib_database):

    # Note: only add search_results if their hash_id is not already
    # in bib_database (important for parallel load_entries())
    save_imported_hash_ids(bib_database)

    pool = mp.Pool(processes=CPUS)
    additional_records = pool.map(load_entries, utils.get_bib_files())
    additional_records = list(chain(*additional_records))

    # do not import records with status=needs_manual_completion
    # note: this cannot be done based on imported_hash_ids
    # (because the record is not complete enough for hash_id creation)
    # but we can use the 'source_file_path' and 'source_id' fields instead
    non_complete_sources = [[entry['source_file_path'], entry['source_id']] for
                            entry in bib_database.entries
                            if 'needs_manual_completion' == entry['status']]
    additional_records = \
        [x for x in additional_records if
         not any((x['source_file_path'] == key and x['ID'] == value)
                 for [key, value] in non_complete_sources)]

    return additional_records


def load(bib_database):

    additional_records = load_additional_records(bib_database)

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
            del entry['source_file_path']
            entry.update(status='imported')

    if os.path.exists('imported_hash_ids.csv'):
        os.remove('imported_hash_ids.csv')

    return additional_records


def create_commit(r, bib_database, details_commit):

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)] or \
            MAIN_REFERENCES in r.untracked_files:
        # to avoid failing pre-commit hooks
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        utils.save_bib_file(bib_database, MAIN_REFERENCES)

        if os.path.exists('search/completion_edits.csv'):
            r.index.add(['search/completion_edits.csv'])

        r.index.add([MAIN_REFERENCES])
        r.index.add(utils.get_bib_files())
        hook_skipping = 'false'
        if not DEBUG_MODE:
            hook_skipping = 'true'
        r.index.commit(
            '⚙️ Import search results \n - ' +
            '\n - '.join(details_commit) +
            '\n - ' + utils.get_package_details(),
            author=git.Actor(
                'script:importer.py', ''),
            skip_hooks=hook_skipping
        )
    else:
        print('No new records added to MAIN_REFERENCES')
    return
