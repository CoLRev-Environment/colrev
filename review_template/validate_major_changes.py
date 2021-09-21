#! /usr/bin/env python
import datetime

import bibtexparser
import dictdiffer
import git
import yaml
from bibtexparser.bibdatabase import BibDatabase

from review_template import entry_hash_function
from review_template import process_duplicates

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']


def main():
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
            current_bib_database = bibtexparser.loads(filecontents)
            found = True

    change_significance = []

    for current_entry in current_bib_database.entries:
        for current_hash_id in current_entry['hash_id'].split(','):
            prior_entries = [x for x in prior_bib_database.entries
                             if current_hash_id in x['hash_id'].split(',')]
            for prior_entry in prior_entries:
                similarity = \
                    process_duplicates.get_entry_similarity(current_entry,
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
        current_entry = [x for x in current_bib_database.entries
                         if current_hash_id in x['hash_id'].split(',')]

        db = BibDatabase()
        db.entries = prior_entry
        print(bibtexparser.dumps(db))
        db = BibDatabase()
        db.entries = current_entry
        print(bibtexparser.dumps(db))

        for diff in list(dictdiffer.diff(prior_entry, current_entry)):
            # Note: may treat fields differently (e.g., status, ...)
            print(diff)
        print(' ------------------------ ')
        input('TODO: correct? if not, replace current entry with the old one')


if __name__ == '__main__':
    main()
