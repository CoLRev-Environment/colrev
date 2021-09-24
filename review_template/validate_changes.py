#! /usr/bin/env python
import itertools
import os
import pprint

import bibtexparser
import dictdiffer
import git
import yaml

from review_template import entry_hash_function
from review_template import importer
from review_template import process_duplicates
from review_template import utils

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']


def get_search_entries():
    bib_files = utils.get_bib_files()
    search_entries = importer.get_db_with_completion_edits(bib_files.pop())
    for bib_file in bib_files:
        add_search_entries = importer.get_db_with_completion_edits(bib_file)
        [search_entries.entries.append(x) for x in add_search_entries.entries]

    # No need to check sufficiently_complete metadata:
    # incomplete records should not be merged.
    for entry in search_entries.entries:
        hid = entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)
        entry.update(hash_id=hid)
        del entry['source_file_path']

    return search_entries


def validate_cleansing_changes(bib_database, search_entries):

    print('Calculating cleansing differences...')
    change_difference = []
    for entry in bib_database.entries:
        if 'changed_in_target_commit' not in entry:
            continue
        for current_hash_id in entry['hash_id'].split(','):
            prior_entries = [x for x in search_entries.entries
                             if current_hash_id in x['hash_id'].split(',')]
            for prior_entry in prior_entries:
                similarity = \
                    process_duplicates.get_entry_similarity(entry,
                                                            prior_entry)
                change_difference.append([current_hash_id, similarity])

    change_difference = [[x, y] for [x, y] in change_difference if y < 1]
    # sort according to similarity
    change_difference.sort(key=lambda x: x[1])

    if 0 == len(change_difference):
        print('No substantial differences found.')

    pp = pprint.PrettyPrinter(indent=4)

    for current_hash_id, similarity in change_difference:
        # Escape sequence to clear terminal output for each new comparison
        print(chr(27) + '[2J')
        print('Entry hash_id: ' + current_hash_id)

        print('Difference: ' + str(round(1-similarity, 4)) + '\n\n')
        entry_1 = [x for x in search_entries.entries
                   if current_hash_id == x['hash_id']]
        pp.pprint(entry_1[0])
        entry_2 = [x for x in bib_database.entries
                   if current_hash_id in x['hash_id']]
        pp.pprint(entry_2[0])

        print('\n\n')
        for diff in list(dictdiffer.diff(entry_1, entry_2)):
            # Note: may treat fields differently (e.g., status, ID, ...)
            pp.pprint(diff)

        if 'n' == input('continue (y/n)?'):
            break
        # input('TODO: correct? if not, replace current entry with old one')

    return


def validate_merging_changes(bib_database, search_entries):

    os.system('cls' if os.name == 'nt' else 'clear')
    print('Calculating differences between merged records...')
    change_difference = []
    merged_entries = False
    for entry in bib_database.entries:
        if 'changed_in_target_commit' not in entry:
            continue
        if ',' in entry['hash_id']:
            merged_entries = True
            duplicate_hid_pairs = \
                list(itertools.combinations(entry['hash_id'].split(','), 2))
            for hash_id_1, hash_id_2 in duplicate_hid_pairs:
                entry_1 = [x for x in search_entries.entries
                           if hash_id_1 == x['hash_id']]
                entry_2 = [x for x in search_entries.entries
                           if hash_id_2 == x['hash_id']]

                similarity = \
                    process_duplicates.get_entry_similarity(entry_1[0],
                                                            entry_2[0])
                change_difference.append([hash_id_1, hash_id_2, similarity])

    change_difference = [[x, y, z]
                         for [x, y, z] in change_difference if z < 1]

    # sort according to similarity
    change_difference.sort(key=lambda x: x[2])

    if 0 == len(change_difference):
        if merged_entries:
            print('No substantial differences found.')
        else:
            print('No merged entries')

    pp = pprint.PrettyPrinter(indent=4)

    for hash_id_1, hash_id_2, similarity in change_difference:
        # Escape sequence to clear terminal output for each new comparison
        print(chr(27) + '[2J')

        print('Differences between merged entries: ' +
              str(round(1-similarity, 4)) + '\n\n')
        entry_1 = [x for x in search_entries.entries
                   if hash_id_1 == x['hash_id']]
        pp.pprint(entry_1[0])
        entry_2 = [x for x in search_entries.entries
                   if hash_id_2 == x['hash_id']]
        pp.pprint(entry_2[0])

        if 'n' == input('continue (y/n)?'):
            break
        # TODO: explain users how to change it/offer option to reverse!

    return


def load_bib_database(target_commit):

    if 'none' == target_commit:
        print('Loading data...')
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        [x.update(changed_in_target_commit='True')
            for x in bib_database.entries]

    else:
        print('Loading data from history...')
        repo = git.Repo()

        revlist = (
            (commit.hexsha, (commit.tree / MAIN_REFERENCES).data_stream.read())
            for commit in repo.iter_commits(paths=MAIN_REFERENCES)
        )
        found = False
        for commit, filecontents in list(revlist):
            if found:  # load the MAIN_REFERENCES in the following commit
                prior_bib_database = bibtexparser.loads(filecontents)
                break
            if commit == target_commit:
                bib_database = bibtexparser.loads(filecontents)
                found = True

        # determine which entries have been changed (cleansed or merged)
        # in the target_commit
        for entry in bib_database.entries:
            prior_entry = [x for x in prior_bib_database.entries
                           if x['ID'] == entry['ID']][0]
            if entry != prior_entry:
                entry.update(changed_in_target_commit='True')

    assert all('hash_id' in x for x in bib_database.entries)

    return bib_database


def main(scope, target_commit):

    bib_database = load_bib_database(target_commit)

    # Note: search entries are considered immutable
    # we therefore load the latest files
    search_entries = get_search_entries()

    if 'cleanse' == scope or 'all' == scope:
        validate_cleansing_changes(bib_database, search_entries)

    if 'merge' == scope or 'all' == scope:
        validate_merging_changes(bib_database, search_entries)


if __name__ == '__main__':
    main()
