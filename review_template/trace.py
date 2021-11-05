#! /usr/bin/env python
import logging
import pprint
import time

import bibtexparser
import dictdiffer
import git

from review_template import repo_setup

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)


MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
DATA = repo_setup.paths['DATA']


def main(ID):

    print(f'Trace record by ID: {ID}')

    repo = git.Repo()

    revlist = repo.iter_commits()

    pp = pprint.PrettyPrinter(indent=4)

    prev_record, prev_data = [], ''
    for commit in reversed(list(revlist)):
        commit_message_first_line = commit.message.partition('\n')[0]
        print('\n\nCommit: ' +
              f'{commit} - {commit_message_first_line}' +
              f' {commit.author.name} ' +
              time.strftime(
                  '%a, %d %b %Y %H:%M',
                  time.gmtime(commit.committed_date),
              )
              )

        if (MAIN_REFERENCES in commit.tree):
            filecontents = (commit.tree / MAIN_REFERENCES).data_stream.read()
            individual_bib_db = bibtexparser.loads(filecontents)
            record = [
                record for record in individual_bib_db.entries
                if record['ID'] == ID
            ]

            if len(record) == 0:
                print(f'record {ID} not in commit.')
            else:
                diffs = list(dictdiffer.diff(prev_record, record))
                if len(diffs) > 0:
                    for diff in diffs:
                        pp.pprint(diff)
                prev_record = record

        if (DATA in commit.tree):
            filecontents = (commit.tree / DATA).data_stream.read()
            for line in str(filecontents).split('\\n'):
                if ID in line:
                    if line != prev_data:
                        print(f'Data: {line}')
                        prev_data = line

    return


if __name__ == '__main__':
    main()
