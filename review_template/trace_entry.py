#! /usr/bin/env python
import logging
import pprint
import time

import bibtexparser
import dictdiffer
import git
import yaml

from review_template import entry_hash_function

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']
SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
DATA = entry_hash_function.paths[HASH_ID_FUNCTION]['DATA']


def main(citation_key):

    print('Trace entry by citation_key: ' + citation_key)

    repo = git.Repo()

    # TODO: trace_hash and list individual search results

    revlist = repo.iter_commits()

    pp = pprint.PrettyPrinter(indent=4)

    prev_entry = []
    prev_screen = ''
    prev_data = ''
    for commit in reversed(list(revlist)):

        print('\n\nCommit: ' +
              str(commit),
              ' - ',
              commit.message.partition('\n')[0],
              ' ',
              commit.author.name,
              ' ',
              time.strftime(
                  '%a, %d %b %Y %H:%M',
                  time.gmtime(commit.committed_date),
              ),
              )

        if (MAIN_REFERENCES in commit.tree):
            filecontents = (commit.tree / MAIN_REFERENCES).data_stream.read()
            individual_bib_database = bibtexparser.loads(filecontents)
            entry = [
                entry for entry in individual_bib_database.entries
                if entry['ID'] == citation_key
            ]

            if len(entry) == 0:
                print('Entry ' + citation_key + ' not in commit.')
            else:
                diffs = list(dictdiffer.diff(prev_entry, entry))
                if len(diffs) > 0:
                    for diff in diffs:
                        pp.pprint(diff)
                prev_entry = entry

        if (SCREEN in commit.tree):
            filecontents = (commit.tree / SCREEN).data_stream.read()
            for line in str(filecontents).split('\\n'):
                if citation_key in line:
                    if line != prev_screen:
                        print('Screen: ' + line)
                        prev_screen = line

        if (DATA in commit.tree):
            filecontents = (commit.tree / DATA).data_stream.read()
            for line in str(filecontents).split('\\n'):
                if citation_key in line:
                    if line != prev_data:
                        print('Data: ' + line)
                        prev_data = line


if __name__ == '__main__':
    main()
