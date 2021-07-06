#! /usr/bin/env python
import hashlib
import re

import bibtexparser
import config
import entry_hash_function
import utils
from bibtexparser.customization import convert_to_unicode

MAIN_REFERENCES = config.paths['MAIN_REFERENCES']
BIB_DETAILS_PATH = config.paths['BIB_DETAILS_PATH']


def robust_append(string_to_hash, to_append):

    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub(r'\s+', ' ', to_append)
    to_append = to_append.lower()

    string_to_hash = string_to_hash + to_append

    return string_to_hash


def get_container_title(entry):
    container_title = ''
    # the latter fields take precedence
    if 'series' in entry:
        container_title = entry['series']
    if 'booktitle' in entry:
        container_title = entry['booktitle']
    if 'journal' in entry:
        container_title = entry['journal']
    return container_title


def old_create_hash_function(entry):
    # TODO: maybe include the version of the hash_function
    # as the first part of string_to_hash? This would prevent cases
    # in which almost all hash_ids are identical (and very few hash_ids change)
    # when updatingthe hash function
    # (this may look like an anomaly and be hard to explain)
    # TODO: format authors (discuss: could this create challenges?)
    string_to_hash = robust_append('', entry.get('author', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('year', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('title', ''))
    string_to_hash = robust_append(string_to_hash, get_container_title(entry))
    string_to_hash = robust_append(string_to_hash, entry.get('volume', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('number', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('pages', ''))

    # TODO: revise, considering different types of bib-entries, examples
    # book: publisher? (NO!) editor??
    # organization (manual) institution (tech.report)
    # school (thesis?) - as the container title for theses?
    # howpublished/url for misc/electronic: -> container title?
    # include type (thesis/article/...)?

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()


def replace_hash_ids(bib_file):
    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        pairs = []
        for entry in individual_bib_database.entries:
            old_hash = old_create_hash_function(entry)
            old_hash_prefixed = 'old_hash_' + old_hash
            new_hash = entry_hash_function.create_hash(entry)
            pairs.append([old_hash_prefixed, new_hash])

        if old_hash == new_hash:
            print('old_hash == new_hash (identical hash function?)')

        # replace in MAIN_REFERENCES
        with open(MAIN_REFERENCES) as file:
            filedata = file.read()

        for old_hash_prefixed, new_hash in pairs:
            filedata = filedata.replace(old_hash_prefixed, new_hash)

        with open(MAIN_REFERENCES, 'w') as file:
            file.write(filedata)

        # replace in BIB_DETAILS_PATH
        with open(BIB_DETAILS_PATH) as file:
            filedata = file.read()

        for old_hash_prefixed, new_hash in pairs:
            filedata = filedata.replace(old_hash_prefixed, new_hash)

        with open(BIB_DETAILS_PATH, 'w') as file:
            file.write(filedata)

    return


def prefix_old_hash_ids(bib_file):

    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        pairs = []
        for entry in individual_bib_database.entries:
            old_hash = old_create_hash_function(entry)
            old_hash_prefixed = 'old_hash_' + old_hash
            pairs.append([old_hash, old_hash_prefixed])

        # replace in MAIN_REFERENCES
        with open(MAIN_REFERENCES) as file:
            filedata = file.read()

        for old_hash, old_hash_prefixed in pairs:

            filedata = filedata.replace(old_hash, old_hash_prefixed)\
                .replace('old_hash_old_hash_', 'old_hash_')

        with open(MAIN_REFERENCES, 'w') as file:
            file.write(filedata)

        # replace in BIB_DETAILS_PATH
        with open(BIB_DETAILS_PATH) as file:
            filedata = file.read()

        for old_hash, old_hash_prefixed in pairs:

            filedata = filedata.replace(old_hash, old_hash_prefixed)\
                .replace('old_hash_old_hash_', 'old_hash_')

        with open(BIB_DETAILS_PATH, 'w') as file:
            file.write(filedata)

    return


if __name__ == '__main__':

    print('')
    print('')

    print('Renew hash_ids')
    print('')
    print('Note: replace the content of the old_create_hash_function ',
          'and robust_append) in this file (renew_hash_id.py)')

    input('TBD: retrieve script from git history and import for the renewal??')

    # Warn if "old_hash_" in any of the files
    with open(MAIN_REFERENCES) as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in MAIN_REFERENCES')

    with open(BIB_DETAILS_PATH) as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in BIB_DETAILS_PATH')

    input('Check: git clean state?')
    input('CHECK: will hash_ids be replaced in al relevant files? ')
    # (perhaps replace in all files, not just selected ones?)

    # To avoid creating odl/new hash_collisions in the replacement process,
    # create prefixes for the old hash_ids
    for bib_file in utils.get_bib_files():
        prefix_old_hash_ids(bib_file)

    for bib_file in utils.get_bib_files():
        replace_hash_ids(bib_file)

    # Warn if "old_hash_" in any of the files
    with open(MAIN_REFERENCES) as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in MAIN_REFERENCES')

    with open(BIB_DETAILS_PATH) as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in BIB_DETAILS_PATH')
