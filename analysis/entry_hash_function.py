#!/usr/bin/env python3
import hashlib
import re

from nameparser import HumanName

HASH_FUNCTION_VERSION = 'v_0.1'


def robust_append(string_to_hash, to_append):
    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub(r'\s+', ' ', to_append)
    to_append = to_append.lower()
    string_to_hash = string_to_hash + to_append
    return string_to_hash


def mostly_upper_case(input_string):
    input_string = input_string.replace('.', '').replace(',', '')
    words = input_string.split()
    return sum(word.isupper() for word in words)/len(words) > 0.8


def format_author_field(input_string):
    names = input_string.split(' and ')
    author_string = ''
    for name in names:
        # Note: https://github.com/derek73/python-nameparser
        # is very effective (maybe not perfect)
        parsed_name = HumanName(name)
        if mostly_upper_case(input_string
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


def get_container_title(entry):

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

    if 'url' in entry and not any(x in entry for x in ['journal', 'series', 'booktitle']):
        container_title += entry['url']

    return container_title


def unify_pages_field(input_string):
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


def create_hash(entry):

    # Including the version of the hash_function prevents cases
    # in which almost all hash_ids are identical (and very few hash_ids change)
    # when updatingthe hash function
    # (this may look like an anomaly and be hard to identify)
    string_to_hash = HASH_FUNCTION_VERSION
    author = entry.get('author', '')
    string_to_hash = robust_append(string_to_hash, format_author_field(author))
    string_to_hash = robust_append(string_to_hash, entry.get('year', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('title', ''))
    string_to_hash = robust_append(string_to_hash, get_container_title(entry))
    string_to_hash = robust_append(string_to_hash, entry.get('volume', ''))
    string_to_hash = robust_append(string_to_hash, entry.get('number', ''))
    pages = entry.get('pages', '')
    string_to_hash = robust_append(string_to_hash, unify_pages_field(pages))

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
