#!/usr/bin/env python3
import hashlib
import re
import unicodedata

from nameparser import HumanName

# Note: including the paths here is useful to ensure that a passing pre-commit
# means that the files are in the specified places. This is particularly
# important for gathering crowd-sourced data across review repositories.


#############################################################################

# v_0.1

paths_v_0_1 = dict(
    MAIN_REFERENCES='references.bib',
    SCREEN='screen.csv',
    DATA='data.csv',
    PDF_DIRECTORY='pdfs/',
    SEARCH_DETAILS='search/search_details.csv'
)


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

paths_v_0_2 = dict(
    MAIN_REFERENCES='references.bib',
    SCREEN='screen.csv',
    DATA='data.csv',
    PDF_DIRECTORY='pdfs/',
    SEARCH_DETAILS='search/search_details.csv'
)

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


paths_v_0_3 = dict(
    MAIN_REFERENCES='references.bib',
    SCREEN='screen.csv',
    DATA='data.csv',
    PDF_DIRECTORY='pdfs/',
    SEARCH_DETAILS='search/search_details.csv'
)

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


paths = \
    {'v_0.1': paths_v_0_1,
     'v_0.2': paths_v_0_2,
     'v_0.3': paths_v_0_3}

create_hash = \
    {'v_0.1': create_hash_function_v_0_1,
     'v_0.2': create_hash_function_v_0_2,
     'v_0.3': create_hash_function_v_0_3}
