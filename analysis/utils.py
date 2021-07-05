#!/usr/bin/env python3
import hashlib
import os
import re
import sys
import unicodedata
from pathlib import Path
from string import ascii_lowercase

import bibtexparser
import pandas as pd
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode
from git import Repo

from nameparser import HumanName


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

def create_hash(entry):
    # TODO: maybe include the version of the hash_function as the first part of string_to_hash? This would prevent cases in which almost all hash_ids are identical (and very few hash_ids change) when updatingthe hash function (this may look like an anomaly and be hard to explain)
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


def rmdiacritics(char):
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


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    wo_ac = [
        rmdiacritics(c)
        for c in nfkd_form if not unicodedata.combining(c)
    ]
    wo_ac = ''.join(wo_ac)
    return wo_ac


class CitationKeyPropagationError(Exception):
    pass

def get_hash_ids(bib_database):

    hash_id_list = []
    for entry in bib_database.entries:
        if 'hash_id' in entry:
            if ',' in entry['hash_id']:
                hash_id_list = hash_id_list + entry['hash_id'].split(',')
            else:
                hash_id_list = hash_id_list + [entry['hash_id']]

    return hash_id_list

def propagated_citation_key(citation_key):

    propagated = False

    if os.path.exists('data/screen.csv'):
        screen = pd.read_csv('data/screen.csv', dtype=str)
        if citation_key in screen['citation_key'].tolist():
            propagated = True

    if os.path.exists('data/data.csv'):
        # Note: this may be redundant, but just to be sure:
        data = pd.read_csv('data/data.csv', dtype=str)
        if citation_key in data['citation_key'].tolist():
            propagated = True

    # TODO: also check data_pages?

    return propagated


def generate_citation_key(entry, bib_database, raise_error=True):

    # Make sure that citation_keys that have been propagated to the
    # screen or data will not be replaced
    # (this would break the chain of evidence)
    if propagated_citation_key(entry['ID']) and raise_error:
        raise CitationKeyPropagationError(
            'WARNING: do not change citation_keys that have been ',
            'propagated to screen.csv and/or data.csv (' +
            entry['ID'] + ')',
        )

    if ',' in entry.get('author', ''):
        temp_citation_key = entry.get('author', '')\
            .split(',')[0].replace(' ', '') +\
            entry.get('year', '')
    else:
        temp_citation_key = entry.get('author', '')\
            .split(' ')[0] +\
            entry.get('year', '')
    
    if temp_citation_key.isupper():
        temp_citation_key = temp_citation_key.capitalize()
    # Replace special characters
    # (because citation_keys may be used as file names)
    temp_citation_key = remove_accents(temp_citation_key)
    temp_citation_key = re.sub('\(.*\)', '', temp_citation_key)
    temp_citation_key = re.sub('[^0-9a-zA-Z]+', '', temp_citation_key)
    letters = iter(ascii_lowercase)

    # make sure that there are no other entries with the same ID
    # TODO: we might have to split the x[hash_id] and the entry.get(hash_id, )
    other_ids = [
        x['ID'] for x in bib_database.entries
        if x['ID'] != entry['ID']
    ]
    while temp_citation_key in other_ids:
        next_letter = next(letters)
        if next_letter == 'a':
            temp_citation_key = temp_citation_key + next_letter
        else:
            temp_citation_key = temp_citation_key[:-1] + next_letter

    return temp_citation_key

def mostly_upper_case(input_string):
    input_string = input_string.replace('.', '').replace(',','')
    words = input_string.split()
    return sum(word.isupper() for word in words)/len(words) > 0.8

def title_if_mostly_upper_case(input_string):
    words = input_string.split()
    if sum(word.isupper() for word in words)/len(words) > 0.8:
        return input_string.capitalize()
    else:
        return input_string

def format_author_field(input_string):
    
    names = input_string.split(' and ')
    author_string = ''
    for name in names:
        # Note: https://github.com/derek73/python-nameparser
        # is very effective (maybe not perfect)
        parsed_name = HumanName(name)
        # TODO: if all capitalized:
        # utils.mostly_upper_case(author_string.replace(' and ', '').replace('Jr',''))
        # https://nameparser.readthedocs.io/en/latest/usage.html#capitalization-support
        # name.capitalize(force=True)
        parsed_name.string_format = "{last} {suffix}, {first} ({nickname}) {middle}"
        # .capitalize(force=True)
        if author_string == '':
            author_string = str(parsed_name).replace(' , ', ', ')
        else:
            author_string = author_string + ' and ' + str(parsed_name).replace(' , ', ', ')

    return author_string

def unify_pages_field(input_string):
    if not isinstance(input_string, str):
        return input_string
    if not re.match(r'^\d*--\d*$', input_string) and not '--' in input_string:
        input_string = input_string\
                        .replace('-', '--')\
                        .replace('–', '--')\
                        .replace('----', '--')\
                        .replace(' -- ', '--')\
                        .rstrip('.')

    if not re.match(r'^\d*$', input_string) and \
       not re.match(r'^\d*--\d*$', input_string) and\
       not re.match(r'^[xivXIV]*--[xivXIV]*$', input_string):
        print('Unusual pages: ' + input_string)
    return input_string

def validate_search_details():

    search_details = pd.read_csv('data/search/search_details.csv')

    # check columns
    predef_colnames = {
        'filename',
        'number_records',
        'iteration',
        'date_start',
        'date_completion',
        'source_url',
        'search_parameters',
        'responsible',
        'comment',
    }
    if not set(search_details.columns) == predef_colnames:
        print(
            'Problem: columns in search/search_details.csv ',
            'not matching predefined colnames',
        )
        print(set(search_details.columns))
        print('Should be')
        print(predef_colnames)
        print('')
        sys.exit()

    # TODO: filenames should exist, all files should have
    # a row, iteration, number_records should be int, start

    return


def validate_bib_file(filename):

    # Do not load/warn when bib-file contains the field "Early Access Date"
    # https://github.com/sciunto-org/python-bibtexparser/issues/230

    with open(filename) as bibfile:
        if 'Early Access Date' in bibfile.read():
            print(
                'Error while loading the file: ',
                'replace Early Access Date in bibfile before loading!',
            )
            return False

    # check number_records matching search_details.csv
    search_details = pd.read_csv('data/search/search_details.csv')
    try:
        records_expected = search_details.loc[
            search_details['filename'] == Path(
                filename,
            ).name
        ].number_records.item()
        with open(filename) as bibtex_file:
            bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True,
            ).parse_file(bibtex_file, partial=True)

        if len(bib_database.entries) != records_expected:
            print(
                'Error while loading the file: number of records imported ',
                'not identical to search/search_details.csv$number_records',
            )
            print('Loaded: ' + str(len(bib_database.entries)))
            print('Expected: ' + str(records_expected))
            return False
    except ValueError:
        print(
            'WARNING: no details on ',
            filename,
            ' provided in data/search/search_details.csv',
        )
        pass
    return True


def load_references_bib(modification_check=True, initialize=False):

    references_bib_path = 'data/references.bib'
    if os.path.exists(os.path.join(os.getcwd(), references_bib_path)):
        if modification_check:
            git_modification_check('references.bib')
        with open(references_bib_path) as target_db:
            references_bib = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True,
            ).parse_file(target_db, partial=True)
    else:
        if initialize:
            references_bib = BibDatabase()
        else:
            print('data/reference.bib does not exist')
            sys.exit()

    return references_bib


def git_modification_check(filename):

    repo = Repo('data')
    # hcommit = repo.head.commit
    # if 'references.bib' in [entry.a_path for entry in hcommit.diff(None)]:
    # print('commit changes in references.bib before executing script?')
    index = repo.index
    if filename in [entry.a_path for entry in index.diff(None)]:
        print(
            'WARNING: There are changes in ',
            filename,
            ' that are not yet added to the git index. ',
            'They may be overwritten by this script. ',
            'Please consider to MANUALLY add the ' +
            filename,
            ' to the index before executing script.',
        )
        if 'y' != input('override changes (y/n)?'):
            sys.exit()

    return


def get_bib_files():
    bib_files = []

    for (dirpath, dirnames, filenames) in \
            os.walk(os.path.join(os.getcwd(), 'data/search/')):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)\
                .replace('/opt/workdir/', '')
            if file_path.endswith('.bib'):
                if not validate_bib_file(file_path):
                    continue
                bib_files = bib_files + [file_path]
    return bib_files


def save_bib_file(bib_database, target_file):

    writer = BibTexWriter()

    writer.contents = ['entries', 'comments']
    writer.indent = '  '
    writer.display_order = [
        'author',
        'booktitle',
        'journal',
        'title',
        'year',
        'editor',
        'number',
        'pages',
        'series',
        'volume',
        'abstract',
        'book-author',
        'book-group-author',
        'doi',
        'file',
        'hash_id',
    ]

    writer.order_entries_by = ('ID', 'author', 'year')
    writer.add_trailing_comma = True
    writer.align_values = True
    bibtex_str = bibtexparser.dumps(bib_database, writer)

    with open(target_file, 'w') as out:
        out.write(bibtex_str + '\n')

    return


def get_included_papers():

    bibtex_file = 'data/references.bib'
    assert os.path.exists(bibtex_file)

    screen_file = 'data/screen.csv'
    assert os.path.exists(screen_file)

    pdfs = []

    screen = pd.read_csv(screen_file, dtype=str)

    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    for record_id in screen['citation_key'].tolist():

        with open(bibtex_file) as bib_file:
            bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True,
            ).parse_file(bib_file, partial=True)

            for entry in bib_database.entries:
                if entry.get('ID', '') == record_id:
                    if 'file' in entry:
                        filename = entry['file'].replace('.pdf:PDF', '.pdf')\
                                                .replace(':', '')
                        pdf_path = os.path.join(os.getcwd(), filename)
                        if os.path.exists(pdf_path):
                            pdfs.append(entry['ID'])
                        else:
                            print(
                                '- Error: file not available ',
                                entry['file'],
                                ' (',
                                entry['ID'],
                                ')',
                            )

    return pdfs
