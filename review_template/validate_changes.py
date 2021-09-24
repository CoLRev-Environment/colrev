#! /usr/bin/env python
import datetime
import itertools
import pprint

import bibtexparser
import dictdiffer
import git
import yaml
from bibtexparser.bibdatabase import BibDatabase

from review_template import entry_hash_function
from review_template import importer
from review_template import process_duplicates
from review_template import utils

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']


def validate_merging_changes():

    bib_database = utils.load_references_bib(
        modification_check=False, initialize=False,
    )

    change_significance = []

    bib_database.entries = [x for x in bib_database.entries if 'hash_id' in x]

    bib_files = utils.get_bib_files()
    db = importer.get_db_with_completion_edits(bib_files.pop())
    for bib_file in bib_files:
        add_db = importer.get_db_with_completion_edits(bib_file)
        [db.entries.append(x) for x in add_db.entries]

    # TODO: check sufficiently complete!? (not necessarily - incomplete records
    # should not be merged...)
    for entry in db.entries:
        hid = entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)
        entry.update(hash_id=hid)

    for entry in bib_database.entries:
        if ',' in entry['hash_id']:
            duplicate_hid_pairs = \
                list(itertools.combinations(entry['hash_id'].split(','), 2))
            for hash_id_1, hash_id_2 in duplicate_hid_pairs:
                entry_1 = [x for x in db.entries if hash_id_1 == x['hash_id']]
                entry_2 = [x for x in db.entries if hash_id_2 == x['hash_id']]

                similarity = \
                    process_duplicates.get_entry_similarity(entry_1[0],
                                                            entry_2[0])
                change_significance.append([hash_id_1, hash_id_2, similarity])

    change_significance = [[x, y, z]
                           for [x, y, z] in change_significance if z < 1]

    # sort according to similarity
    change_significance.sort(key=lambda x: x[2])
    # print(change_significance[0:30])

    pp = pprint.PrettyPrinter(indent=4)

    for hash_id_1, hash_id_2, similarity in change_significance:
        # Escape sequence to clear terminal output for each new comparison
        print(chr(27) + '[2J')

        print('Similarity of merged entries: ' + str(similarity) + '\n\n')
        entry_1 = [x for x in db.entries if hash_id_1 == x['hash_id']]
        pp.pprint(entry_1[0])
        entry_2 = [x for x in db.entries if hash_id_2 == x['hash_id']]
        pp.pprint(entry_2[0])

        input('continue?')
        # TODO: explain users how to change it/offer option to reverse!

    return


def validate_cleansing_changes():

    repo = git.Repo()

    revlist = (
        (commit, (commit.tree / MAIN_REFERENCES).data_stream.read())
        for commit in repo.iter_commits(paths=MAIN_REFERENCES)
    )

    commits_for_checking = []
    for commit, filecontents in reversed(list(revlist)):
        # if 'cleanse_records.py' in commit.author.name:
        commits_for_checking.append(commit)

    if len(commits_for_checking) > 1:
        nr = 1
        for commit in commits_for_checking:
            print(nr, datetime.datetime.fromtimestamp(commit.committed_date),
                  ' - ', commit.message.replace('\n', ' '))
            nr += 1
        print('\n')
        selection = int(input('select the commit that should be checked:'))
        assert isinstance(selection, int)
        commits_for_checking = [commits_for_checking[int(selection-1)]]

    revlist = (
        (commit, (commit.tree / MAIN_REFERENCES).data_stream.read())
        for commit in repo.iter_commits(paths=MAIN_REFERENCES)
    )
    found = False
    for commit, filecontents in list(revlist):
        if found:  # load the MAIN_REFERENCES in the following commit
            prior_bib_database = bibtexparser.loads(filecontents)
            break
        if commit == commits_for_checking[0]:
            bib_database = bibtexparser.loads(filecontents)
            found = True

    change_significance = []

    for entry in bib_database.entries:
        for current_hash_id in entry['hash_id'].split(','):
            prior_entries = [x for x in prior_bib_database.entries
                             if current_hash_id in x['hash_id'].split(',')]
            for prior_entry in prior_entries:
                similarity = \
                    process_duplicates.get_entry_similarity(entry,
                                                            prior_entry)
                change_significance.append([current_hash_id, similarity])

    change_significance = [[x, y] for [x, y] in change_significance if y < 1]
    # sort according to similarity
    change_significance.sort(key=lambda x: x[1])
    print(change_significance[0:30])

    for current_hash_id, similarity in change_significance:
        print('\n\n\n\n')
        print(' # # ' + current_hash_id)
        prior_entry = [x for x in prior_bib_database.entries
                       if current_hash_id in x['hash_id'].split(',')]
        entry = [x for x in bib_database.entries
                 if current_hash_id in x['hash_id'].split(',')]

        db = BibDatabase()
        db.entries = prior_entry
        print(bibtexparser.dumps(db))
        db = BibDatabase()
        db.entries = entry
        print(bibtexparser.dumps(db))

        for diff in list(dictdiffer.diff(prior_entry, entry)):
            # Note: may treat fields differently (e.g., status, ...)
            print(diff)
        print(' ------------------------ ')
        input('TODO: correct? if not, replace current entry with the old one')

    return


def main():
    validate_merging_changes()
    validate_cleansing_changes()


if __name__ == '__main__':
    main()
