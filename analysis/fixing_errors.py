#! /usr/bin/env python
import csv
from datetime import datetime

import entry_hash_function
import pandas as pd
import utils
import yaml
from bibtexparser.bibdatabase import BibDatabase

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']
SCREEN_FILE = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
DATA_FILE = entry_hash_function.paths[HASH_ID_FUNCTION]['DATA']


def fix_missing_hash_ids():

    print('')
    print('')

    print('Fix missing hash_ids')
    print('')

#    r = git.Repo()
#
#    if r.is_dirty():
#        print('Commit files before importing new search results.')
#        sys.exit()

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    missing_entry_db = BibDatabase()

    for entry in bib_database.entries:
        if 'hash_id' not in entry:
            entry_wo_hash = entry.copy()
            missing_entry_db.entries.append(entry_wo_hash)
            entry['hash_id'] = \
                entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    missing_entry_file = 'search/' + \
        datetime.today().strftime('%Y-%m-%d') + \
        '-missing_entries.bib'
    if len(missing_entry_db.entries) > 0:
        utils.save_bib_file(missing_entry_db, missing_entry_file)

#    print('Creating commit ...')

#    r.index.add([MAIN_REFERENCES, missing_entry_file])
#    r.index.commit(
#        'Fix missing hash_ids',
#        author=git.Actor('script:fixing_errors.py', ''),
#    )

    return


def rename_propagated_citation_keys():
    print('')
    print('')

    print('Renew propagated citation_keys')
    print('')

#    r = git.Repo()
#
#    if r.is_dirty():
#        print('Commit files before importing new search results.')
#        sys.exit()

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    input('include the list of citation keys in the following line:')
    citation_keys = ['Webster2001', 'Webster2002']
    citation_key_pairs = []
    for entry in bib_database.entries:
        if entry['ID'] in citation_keys:
            replacement = utils.generate_citation_key(
                entry, bib_database, entry_in_bib_db=True,
                raise_error=False)
            citation_key_pairs.append([entry['ID'], replacement])
            entry['ID'] = replacement

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    # replace in screen and data
    screen = pd.read_csv(SCREEN_FILE, dtype=str)
    for old, new in citation_key_pairs:
        screen['citation_key'] = screen['citation_key'].str.replace(
            r'^' + old + '$', new)

    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(
        SCREEN_FILE, index=False,
        quoting=csv.QUOTE_ALL, na_rep='NA',
    )

    data = pd.read_csv(DATA_FILE, dtype=str)
    for old, new in citation_key_pairs:
        data['citation_key'] = data['citation_key'].str.replace(
            r'^' + old + '$', new)

    data.sort_values(by=['citation_key'], inplace=True)
    data.to_csv(
        DATA_FILE,
        index=False,
        quoting=csv.QUOTE_ALL,
        na_rep='NA',
    )


# import fileinput
#    with fileinput.FileInput('search/2021-07-01-references.bib',
#                              inplace=True, backup='.bak') as file:
#        for line in file:
#            for old, new in citation_key_pairs:
#                line = line.replace('{' + old + ',\n', '{' + new + ',\n')
#            print(line, end='')

    return


if __name__ == '__main__':

    # when the referencesb.bib contains entries without hash_ids:
    # this should happen rarely (only when trying to reconstruct an original
    # search-files / MAIN_REFERENCES data set, i.e., without using the
    # main bib file as an import)
    fix_missing_hash_ids()

    rename_propagated_citation_keys()

    # TODO: possible extensions:
    # - remove non-traceable hash_ids
    # - drop entries from missing_entries.bib when another bib_file has
    # identical hash_ids (simpler: remove the generated
    # search-results-bib-file and rerun fix_missing_hash_ids())
