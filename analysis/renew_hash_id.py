#! /usr/bin/env python
import hashlib
import re

import bibtexparser
import utils
from bibtexparser.customization import convert_to_unicode


def robust_append(string_to_hash, to_append):

    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub(r'\s+', ' ', to_append)
    to_append = to_append.lower()

    string_to_hash = string_to_hash + to_append

    return string_to_hash


def old_create_hash_function(entry):
    string_to_hash = robust_append('', entry.get('author', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('author', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('title', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('journal', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('booktitle', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('year', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('volume', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('issue', ''))

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()


def replace_hash_ids(bib_file):
    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        for entry in individual_bib_database.entries:
            old_hash = old_create_hash_function(entry)
            old_hash_prefixed = 'old_hash_' + old_hash
            new_hash = utils.create_hash(entry)

            if old_hash == new_hash:
                print('old_hash == new_hash (identical hash function?)')

            # replace in data/references.bibb
            with open('data/references.bib') as file:
                filedata = file.read()

            filedata = filedata.replace(old_hash_prefixed, new_hash)

            with open('data/references.bib', 'w') as file:
                file.write(filedata)

            # replace in data/search/bib_details.csv
            with open('data/search/bib_details.csv') as file:
                filedata = file.read()

            filedata = filedata.replace(old_hash_prefixed, new_hash)

            with open('data/search/bib_details.csv', 'w') as file:
                file.write(filedata)

    return


def prefix_old_hash_ids(bib_file):

    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        for entry in individual_bib_database.entries:
            old_hash = old_create_hash_function(entry)
            old_hash_prefixed = 'old_hash_' + old_hash

            # replace in data/references.bibb
            with open('data/references.bib') as file:
                filedata = file.read()

            filedata = filedata.replace(old_hash, old_hash_prefixed)\
                .replace('old_hash_old_hash_', 'old_hash_')

            with open('data/references.bib', 'w') as file:
                file.write(filedata)

            # replace in data/search/bib_details.csv
            with open('data/search/bib_details.csv') as file:
                filedata = file.read()

            filedata = filedata.replace(old_hash, old_hash_prefixed)\
                .replace('old_hash_old_hash_', 'old_hash_')

            with open('data/search/bib_details.csv', 'w') as file:
                file.write(filedata)

    return


if __name__ == '__main__':

    print('')
    print('')

    print('Renew hash_id function')
    print('')
    print('Note: replace the content of the old_create_hash_function ',
          'and robust_append) in this file (renew_hash_id.py)')

    # Warn if "old_hash_" in any of the files
    with open('data/references.bib') as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in references.bib')

    with open('data/search/bib_details.csv') as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in data/search/bib_details.csv')

    input('Check: git clean state?')

    # To avoid creating odl/new hash_collisions in the replacement process,
    # create prefixes for the old hash_ids
    for bib_file in utils.get_bib_files():
        prefix_old_hash_ids(bib_file)

    for bib_file in utils.get_bib_files():
        replace_hash_ids(bib_file)

    # Warn if "old_hash_" in any of the files
    with open('data/references.bib') as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in references.bib')

    with open('data/search/bib_details.csv') as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in data/search/bib_details.csv')
