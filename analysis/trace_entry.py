#! /usr/bin/env python
import logging
import time

import bibtexparser
import dictdiffer
import entry_hash_function
import git
import yaml
from bibtexparser.customization import convert_to_unicode

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
DATA = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


def trace_hash(bibfilename, hash_id_needed):
    global nr_found

    with open(bibfilename) as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        for entry in bib_database.entries:
            if entry_hash_function.create_hash[HASH_ID_FUNCTION](entry) == \
                    hash_id_needed:
                print(
                    '\n\n Found hash ',
                    hash_id_needed,
                    '\n in ',
                    bibfilename,
                    '\n\n',
                )
                print(entry)
                nr_found += 1
    return


if __name__ == '__main__':

    print('')
    print('')

    print('Trace entry by citation_key')

    citation_key = input('provide citation_key')
#    citation_key = 'Blijleven2019'

    repo = git.Repo()

    # TODO: trace_hash and list individual search results

    path = MAIN_REFERENCES

    revlist = (
        (commit, (commit.tree / path).data_stream.read())
        for commit in repo.iter_commits(paths=path)
    )
    prev_entry = []

    for commit, filecontents in reversed(list(revlist)):
        print('----------------------------------')
        individual_bib_database = bibtexparser.loads(filecontents)
        entry = [
            entry for entry in individual_bib_database.entries
            if entry['ID'] == citation_key
        ]
        if len(entry) != 0:
            print(
                str(commit),
                ' - ',
                commit.message.replace('\n', ''),
                ' ',
                commit.author.name,
                ' ',
                time.strftime(
                    '%a, %d %b %Y %H:%M',
                    time.gmtime(commit.committed_date),
                ),
            )
            for diff in list(dictdiffer.diff(prev_entry, entry)):
                print(diff)
            prev_entry = entry

    path = SCREEN

    revlist = (
        (commit, (commit.tree / path).data_stream.read())
        for commit in repo.iter_commits(paths=path)
    )

    for commit, filecontents in reversed(list(revlist)):
        print('----------------------------------')
        print(
            str(commit),
            ' - ',
            commit.message.replace('\n', ''),
            ' ',
            commit.author.name,
            ' ',
            time.strftime(
                '%a, %d %b %Y %H:%M',
                time.gmtime(commit.committed_date),
            ),
        )
        for line in str(filecontents).split('\\n'):
            if citation_key in line:
                print(line)

    path = DATA

    revlist = (
        (commit, (commit.tree / path).data_stream.read())
        for commit in repo.iter_commits(paths=path)
    )

    for commit, filecontents in reversed(list(revlist)):
        print('----------------------------------')
        print(
            str(commit),
            ' - ',
            commit.message.replace('\n', ''),
            ' ',
            commit.author.name,
            ' ',
            time.strftime(
                '%a, %d %b %Y %H:%M',
                time.gmtime(commit.committed_date),
            ),
        )
        for line in str(filecontents).split('\\n'):
            if citation_key in line:
                print(line)
