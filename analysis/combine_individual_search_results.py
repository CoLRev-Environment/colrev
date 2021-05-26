#! /usr/bin/env python
import logging
import os
import sys
from string import ascii_lowercase

import bibtexparser
import git
import pandas as pd
import utils
from bibtexparser.customization import convert_to_unicode

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

total_nr_entries_added = 0
total_nr_duplicates_hash_ids = 0
details_commit = []


def get_hash_ids(bib_database):

    hash_id_list = []
    for entry in bib_database.entries:
        if ',' in entry['hash_id']:
            hash_id_list = hash_id_list + entry['hash_id'].split(',')
        else:
            hash_id_list = hash_id_list + [entry['hash_id']]

    return hash_id_list


def gather(bibfilename, bib_database):
    global total_nr_entries_added
    global total_nr_duplicates_hash_ids
    global details_commit
    nr_entries_added = 0
    nr_duplicates_hash_ids = 0

    with open(bibfilename) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        print('')
        print(
            'Loading ' + os.path.basename(bib_file).ljust(52) + '(' +
            str(len(individual_bib_database.entries)).rjust(5) + ' records)',
        )

        for entry in individual_bib_database.entries:

            entry['hash_id'] = utils.create_hash(entry)

            if('abstract' in entry):
                entry['abstract'] = entry['abstract'].replace('\n', ' ')
            if('author' in entry):
                entry['author'] = entry['author'].replace('\n', ' ')
            if('title' in entry):
                entry['title'] = entry['title'].replace('\n', ' ')
            if('booktitle' in entry):
                entry['booktitle'] = entry['booktitle'].replace('\n', ' ')
            if('doi' in entry):
                entry['doi'] = entry['doi'].replace('http://dx.doi.org/', '')
            if('pages' in entry):
                if 1 == entry['pages'].count('-'):
                    entry['pages'] = entry['pages'].replace('-', '--')

            fields_to_keep = [
                'ID', 'hash_id', 'ENTRYTYPE',
                'author', 'year', 'title',
                'journal', 'booktitle', 'series',
                'volume', 'issue', 'number',
                'pages', 'doi', 'abstract',
                'editor', 'book-group-author',
                'book-author', 'keywords',
            ]
            fields_to_drop = [
                'type', 'url', 'organization',
                'issn', 'isbn', 'note',
                'unique-id', 'month', 'researcherid-numbers',
                'orcid-numbers', 'eissn', 'article-number',
                'publisher', 'author_keywords', 'source',
                'affiliation', 'document_type', 'art_number',
            ]
            for val in list(entry):
                if(val not in fields_to_keep):
                    # drop all fields not in fields_to_keep
                    entry.pop(val)
                    # warn if fields are dropped that are not in fields_to_drop
                    if val not in fields_to_drop:
                        print('  dropped ' + val + ' field')

        for entry in individual_bib_database.entries:

            if 0 == len(bib_database.entries):
                bib_database.entries.append(entry)
                total_nr_entries_added += 1
                nr_entries_added += 1

                continue

            if not entry['hash_id'] in get_hash_ids(bib_database):

                # Make sure the ID is unique
                # (otherwise: append letters until this is the case)
                temp_id = entry['ID']
                letters = iter(ascii_lowercase)
                while temp_id in [x['ID'] for x in bib_database.entries]:
                    temp_id = entry['ID'] + next(letters)
                entry['ID'] = temp_id

                bib_database.entries.append(entry)
                total_nr_entries_added += 1
                nr_entries_added += 1

            else:
                total_nr_duplicates_hash_ids += 1
                nr_duplicates_hash_ids += 1

    print(
        ' - ' + str(nr_entries_added).rjust(5) + ' entries added, ' +
        str(nr_duplicates_hash_ids).rjust(5) +
        ' entries with identical hash_ids',
    )

    if nr_entries_added > 0:
        details_commit.append(
            os.path.basename(bib_file),
            ' (',
            str(nr_entries_added),
            ' additional records)',
        )

    return bib_database


if __name__ == '__main__':

    print('')
    print('')

    print('Combine search results')
    print('')
    utils.validate_search_details()

    r = git.Repo('data')

    if not r.is_dirty():
        print('Commit files before importing new search results.')
        sys.exit()

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=True,
    )

    nr_current_entries = len(bib_database.entries)

    if 0 == nr_current_entries:
        print(
            'Created references.bib'.ljust(60),
            '(',
            '0'.rjust(5),
            ' records).',
        )
    else:
        print(
            'Opening existing references.bib '.ljust(60),
            '(',
            str(nr_current_entries).rjust(5),
            ' records)',
        )
    print('')

    print('------------------------------------------------------------------')
    # TODO: define preferences (start by processing e.g., WoS, then GS) or
    # use heuristics to start with the highest quality entries first.
    search_details = pd.read_csv('data/search/search_details.csv')

    for bib_file in utils.get_bib_files():
        bib_database = gather(bib_file, bib_database)

    utils.save_bib_file(bib_database, 'data/references.bib')

    print('')
    print('------------------------------------------------------------------')
    print(
        'Overall: ',
        str(total_nr_entries_added).rjust(5),
        ' records added, ',
        str(len(bib_database.entries)).rjust(5),
        ' records in references.bib',
    )
    print('')

    print('Creating commit ...')

    r.index.add(['references.bib'])
    print('Import search results \n - ' + '\n - '.join(details_commit))
    r.index.commit(
        'Import search results \n - ' + '\n - '.join(details_commit),
        author=git.Actor('script:combine_individual_search_results.py', ''),
    )
