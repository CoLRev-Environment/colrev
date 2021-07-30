#! /usr/bin/env python
import csv
import hashlib
import os
import re
import sys
import unicodedata

import bibtexparser
import entry_hash_function
import git
import utils
import yaml
from bibtexparser.customization import convert_to_unicode
from nameparser import HumanName

MAIN_REFERENCES = entry_hash_function.paths['MAIN_REFERENCES']


#############################################################################

# v_0.1

def robust_append_v_0_1(string_to_hash, to_append):
    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub(r'\s+', ' ', to_append)
    to_append = to_append.lower()
    string_to_hash = string_to_hash + to_append
    return string_to_hash


def mostly_upper_case_v_0_1(input_string):
    input_string = input_string.replace('.', '').replace(',', '')
    words = input_string.split()
    return sum(word.isupper() for word in words)/len(words) > 0.8


def format_author_field_v_0_1(input_string):
    names = input_string.split(' and ')
    author_string = ''
    for name in names:
        # Note: https://github.com/derek73/python-nameparser
        # is very effective (maybe not perfect)
        parsed_name = HumanName(name)
        if mostly_upper_case_v_0_1(input_string
                                   .replace(' and ', '')
                                   .replace('Jr', '')):
            parsed_name.capitalize(force=True)

        parsed_name.string_format = \
            '{last} {suffix}, {first} ({nickname}) {middle}'
        if author_string == '':
            author_string = str(parsed_name).replace(' , ', ', ')
        else:
            author_string = author_string + ' and ' + \
                str(parsed_name).replace(' , ', ', ')

    return author_string


def get_container_title_v_0_1(entry):

    # if multiple container titles are available, they are concatenated
    container_title = ''

    # school as the container title for theses
    if 'school' in entry:
        container_title += entry['school']
    # for technical reports
    if 'institution' in entry:
        container_title += entry['institution']
    if 'series' in entry:
        container_title += entry['series']
    if 'booktitle' in entry:
        container_title += entry['booktitle']
    if 'journal' in entry:
        container_title += entry['journal']

    if 'url' in entry and not any(x in entry for x in ['journal',
                                                       'series',
                                                       'booktitle']):
        container_title += entry['url']

    return container_title


def unify_pages_field_v_0_1(input_string):
    if not isinstance(input_string, str):
        return input_string
    if not re.match(r'^\d*--\d*$', input_string) and '--' not in input_string:
        input_string = input_string\
            .replace('-', '--')\
            .replace('–', '--')\
            .replace('----', '--')\
            .replace(' -- ', '--')\
            .rstrip('.')

    return input_string


def create_hash_function_v_0_1(entry):

    # Including the version of the hash_function prevents cases
    # in which almost all hash_ids are identical (and very few hash_ids change)
    # when updatingthe hash function
    # (this may look like an anomaly and be hard to identify)
    string_to_hash = 'v_0.1'
    author = entry.get('author', '')
    string_to_hash = robust_append_v_0_1(
        string_to_hash, format_author_field_v_0_1(author))
    string_to_hash = robust_append_v_0_1(string_to_hash, entry.get('year', ''))
    string_to_hash = robust_append_v_0_1(
        string_to_hash, entry.get('title', ''))
    string_to_hash = robust_append_v_0_1(
        string_to_hash, get_container_title_v_0_1(entry))
    string_to_hash = robust_append_v_0_1(
        string_to_hash, entry.get('volume', ''))
    string_to_hash = robust_append_v_0_1(
        string_to_hash, entry.get('number', ''))
    pages = entry.get('pages', '')
    string_to_hash = robust_append_v_0_1(
        string_to_hash, unify_pages_field_v_0_1(pages))

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()


#############################################################################

# v_0.2

# Note: the global CONSTANT would interfere with the entry_hash_function.py
# CONSTANTS.string_format = '{last}, {first} {middle}'


# Note: including the paths here is useful to ensure that a passing pre-commit
# means that the files are in the specified places. This is particularly
# important for gathering crowd-sourced data across review repositories.
paths_v_0_2 = dict(
    MAIN_REFERENCES='references.bib',
    SCREEN='screen.csv',
    DATA='data.csv',
    PDF_DIRECTORY='pdfs/',
    BIB_DETAILS='search/bib_details.csv',
    SEARCH_DETAILS='search/search_details.csv'
)


def robust_append_v_0_2(string_to_hash, to_append):
    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub(r'\s+', ' ', to_append)
    to_append = to_append.lower()
    string_to_hash = string_to_hash + to_append
    return string_to_hash


def rmdiacritics_v_0_2(char):
    '''
    Return the base character of char, by "removing" any
    diacritics like accents or curls and strokes and the like.
    '''
    desc = unicodedata.name(char)
    cutoff = desc.find(' WITH ')
    if cutoff != -1:
        desc = desc[:cutoff]
        try:
            char = unicodedata.lookup(desc)
        except KeyError:
            pass  # removing "WITH ..." produced an invalid name
    return char


def remove_accents_v_0_2(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    wo_ac = [
        rmdiacritics_v_0_2(c)
        for c in nfkd_form if not unicodedata.combining(c)
    ]
    wo_ac = ''.join(wo_ac)
    return wo_ac


def format_author_field_v_0_2(input_string):
    input_string = input_string.replace('\n', ' ')
    names = remove_accents_v_0_2(input_string).replace(
        '; ', ' and ').split(' and ')
    author_string = ''
    for name in names:
        parsed_name = HumanName(name)
        parsed_name.string_format = \
            '{last}, {first} {middle}'
        if ',' not in str(parsed_name):
            author_string += str(parsed_name)
            continue
        parsed_name = str(parsed_name).split(', ')
        initials = \
            ''.join(x[0] for x in parsed_name[1].split(' '))
        last_name = parsed_name[0]
        author_string += last_name + initials
    return author_string


def get_container_title_v_0_2(entry):

    # if multiple container titles are available, they are concatenated
    container_title = ''

    # school as the container title for theses
    if 'school' in entry:
        container_title += entry['school']
    # for technical reports
    if 'institution' in entry:
        container_title += entry['institution']
    if 'series' in entry:
        container_title += entry['series']
    if 'booktitle' in entry:
        container_title += entry['booktitle']
    if 'journal' in entry:
        container_title += entry['journal']

    if 'url' in entry and not any(x in entry for x in
                                  ['journal', 'series', 'booktitle']):
        container_title += entry['url']

    return container_title


def unify_pages_field_v_0_2(input_string):
    if not isinstance(input_string, str):
        return input_string
    if not re.match(r'^\d*--\d*$', input_string) and '--' not in input_string:
        input_string = input_string\
            .replace('-', '--')\
            .replace('–', '--')\
            .replace('----', '--')\
            .replace(' -- ', '--')\
            .rstrip('.')

    return input_string


def create_hash_function_v_0_2(entry):

    # Including the version of the hash_function prevents cases
    # in which almost all hash_ids are identical (and very few hash_ids change)
    # when updatingthe hash function
    # (this may look like an anomaly and be hard to identify)
    string_to_hash = 'v_0.2'
    author = entry.get('author', '')
    string_to_hash = robust_append_v_0_2(
        string_to_hash, format_author_field_v_0_2(author))
    string_to_hash = robust_append_v_0_2(string_to_hash, entry.get('year', ''))
    string_to_hash = robust_append_v_0_2(
        string_to_hash, entry.get('title', ''))
    string_to_hash = robust_append_v_0_2(
        string_to_hash, get_container_title_v_0_2(entry))
    string_to_hash = robust_append_v_0_2(
        string_to_hash, entry.get('volume', ''))
    string_to_hash = robust_append_v_0_2(
        string_to_hash, entry.get('number', ''))
    pages = entry.get('pages', '')
    string_to_hash = robust_append_v_0_2(
        string_to_hash, unify_pages_field_v_0_2(pages))

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()

#############################################################################

# v_0.3


# Note: including the paths here is useful to ensure that a passing pre-commit
# means that the files are in the specified places. This is particularly
# important for gathering crowd-sourced data across review repositories.
paths_v_0_3 = dict(
    MAIN_REFERENCES='references.bib',
    SCREEN='screen.csv',
    DATA='data.csv',
    PDF_DIRECTORY='pdfs/',
    SEARCH_DETAILS='search/search_details.csv'
)


def robust_append_v_0_3(string_to_hash, to_append):
    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub(r'\s+', ' ', to_append)
    to_append = to_append.lower()
    string_to_hash = string_to_hash + to_append
    return string_to_hash


def rmdiacritics_v_0_3(char):
    '''
    Return the base character of char, by "removing" any
    diacritics like accents or curls and strokes and the like.
    '''
    desc = unicodedata.name(char)
    cutoff = desc.find(' WITH ')
    if cutoff != -1:
        desc = desc[:cutoff]
        try:
            char = unicodedata.lookup(desc)
        except KeyError:
            pass  # removing "WITH ..." produced an invalid name
    return char


def remove_accents_v_0_3(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    wo_ac = [
        rmdiacritics_v_0_3(c)
        for c in nfkd_form if not unicodedata.combining(c)
    ]
    wo_ac = ''.join(wo_ac)
    return wo_ac


def format_author_field_v_0_3(input_string):
    input_string = input_string.replace('\n', ' ')
    names = remove_accents_v_0_3(input_string).replace(
        '; ', ' and ').split(' and ')
    author_string = ''
    for name in names:
        parsed_name = HumanName(name)
        if ',' not in str(parsed_name):
            author_string += str(parsed_name)
            continue
        # Note: do not set this as a global constant to preserve consistent
        # creation of hash_ids
        parsed_name.string_format = \
            '{last}, {first} {middle}'
        parsed_name = str(parsed_name).split(', ')
        initials = \
            ''.join(x[0] for x in parsed_name[1].split(' '))
        last_name = parsed_name[0]
        author_string += last_name + initials
    return author_string


def get_container_title_v_0_3(entry):

    # if multiple container titles are available, they are concatenated
    container_title = ''

    # school as the container title for theses
    if 'school' in entry:
        container_title += entry['school']
    # for technical reports
    if 'institution' in entry:
        container_title += entry['institution']
    if 'series' in entry:
        container_title += entry['series']
    if 'booktitle' in entry:
        container_title += entry['booktitle']
    if 'journal' in entry:
        container_title += entry['journal']

    if 'url' in entry and not any(x in entry for x in
                                  ['journal', 'series', 'booktitle']):
        container_title += entry['url']

    return container_title


def unify_pages_field_v_0_3(input_string):
    if not isinstance(input_string, str):
        return input_string
    if not re.match(r'^\d*--\d*$', input_string) and '--' not in input_string:
        input_string = input_string\
            .replace('-', '--')\
            .replace('–', '--')\
            .replace('----', '--')\
            .replace(' -- ', '--')\
            .rstrip('.')

    return input_string


def create_hash_function_v_0_3(entry):

    # Including the version of the hash_function prevents cases
    # in which almost all hash_ids are identical (and very few hash_ids change)
    # when updatingthe hash function
    # (this may look like an anomaly and be hard to identify)
    string_to_hash = 'v_0.3'
    author = entry.get('author', '')
    string_to_hash = robust_append_v_0_3(
        string_to_hash, format_author_field_v_0_3(author))
    string_to_hash = robust_append_v_0_3(string_to_hash, entry.get('year', ''))
    string_to_hash = robust_append_v_0_3(
        string_to_hash, entry.get('title', ''))
    string_to_hash = robust_append_v_0_3(
        string_to_hash, get_container_title_v_0_3(entry))
    string_to_hash = robust_append_v_0_3(
        string_to_hash, entry.get('volume', ''))
    string_to_hash = robust_append_v_0_3(
        string_to_hash, entry.get('number', ''))
    pages = entry.get('pages', '')
    string_to_hash = robust_append_v_0_3(
        string_to_hash, unify_pages_field_v_0_3(pages))

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()

#############################################################################


def prefix_old_hash_ids(bib_file):

    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        pairs = []
        for entry in individual_bib_database.entries:
            old_hash = create_hash_function[PRIOR_VERSION](entry)
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

    return


def replace_hash_ids(bib_file):
    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        pairs = []
        for entry in individual_bib_database.entries:
            old_hash = create_hash_function[PRIOR_VERSION](entry)
            old_hash_prefixed = 'old_hash_' + old_hash
            new_hash = create_hash_function[NEW_VERSION](entry)
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

    return


create_hash_function = \
    {'v_0.1': create_hash_function_v_0_1,
     'v_0.2': create_hash_function_v_0_2,
     'v_0.3': create_hash_function_v_0_3}


if __name__ == '__main__':

    print('')
    print('')

    print('Renew hash_ids')
    print('')
    print('Simply change the HASH_ID_FUNCTION in shared_config.yaml')
    print('')

    repo = git.Repo()
    shared_config_path = 'shared_config.yaml'
    revlist = (
        (commit, (commit.tree / shared_config_path).data_stream.read())
        for commit in repo.iter_commits(paths=shared_config_path)
    )
    PRIOR_VERSION = ''
    for commit, filecontents in list(revlist):
        shared_config = yaml.load(filecontents, Loader=yaml.FullLoader)
        PRIOR_VERSION = shared_config['params']['HASH_ID_FUNCTION']
        break

    with open(shared_config_path) as shared_config_yaml:
        shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
    NEW_VERSION = shared_config['params']['HASH_ID_FUNCTION']

    if PRIOR_VERSION == NEW_VERSION:
        print('Please change the HASH_ID_FUNCTION in shared_config.yaml')
        sys.exit()

    print('Changing from ' + PRIOR_VERSION + ' to ' + NEW_VERSION)

    pre_commit_hook_version_id = ''
    with open(os.path.join(sys.path[0],
                           'hash_function_pipeline_commit_id.csv')) \
            as read_obj:
        csv_reader = csv.reader(read_obj)
        for row in csv_reader:
            if row[2] == NEW_VERSION:
                pre_commit_hook_version_id = row[1]

    print('Setting .pre-commit-config.yaml hook-id to ' +
          pre_commit_hook_version_id + ' for ' + NEW_VERSION)

    with open('.pre-commit-config.yaml') as pre_commit_config_yaml:
        pre_commit_config = yaml.load(
            pre_commit_config_yaml, Loader=yaml.FullLoader)
    for hook in pre_commit_config['repos']:
        if hook['repo'] == \
                'https://github.com/geritwagner/pipeline-validation-hooks':
            old_pre_commit_hook_id = hook['rev']

    fin = open('.pre-commit-config.yaml')
    data = fin.read()
    data = data.replace(old_pre_commit_hook_id, pre_commit_hook_version_id)
    fin.close()
    fin = open('.pre-commit-config.yaml', 'wt')
    fin.write(data)
    fin.close()

    repo.index.add(['.pre-commit-config.yaml'])
    repo.index.add([shared_config_path])

    print('\nTODO: check for entries that have no old_hash prefix')
    print('Check: git clean state?')
    print('CHECK: will hash_ids be replaced in al relevant files? ')

    # Warn if "old_hash_" in any of the files
    with open(MAIN_REFERENCES) as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in MAIN_REFERENCES')

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
    else:
        repo.index.add([MAIN_REFERENCES])
