#!/usr/bin/env python3
import io
import os
import pkgutil
import re
import sys
import time
import unicodedata
from importlib.metadata import version
from pathlib import Path
from string import ascii_lowercase

import bibtexparser
import git
import pandas as pd
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode
from git import Repo
from nameparser import HumanName

import docker
from review_template import repo_setup

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
SCREEN = repo_setup.paths['SCREEN']
DATA = repo_setup.paths['DATA']
SEARCH_DETAILS = repo_setup.paths['SEARCH_DETAILS']


def retrieve_local_resources():

    if os.path.exists('lexicon/JOURNAL_ABBREVIATIONS.csv'):
        JOURNAL_ABBREVIATIONS = pd.read_csv(
            'lexicon/JOURNAL_ABBREVIATIONS.csv')
    else:
        JOURNAL_ABBREVIATIONS = pd.DataFrame(
            [], columns=['journal', 'abbreviation'])

    if os.path.exists('lexicon/JOURNAL_VARIATIONS.csv'):
        JOURNAL_VARIATIONS = pd.read_csv('lexicon/JOURNAL_VARIATIONS.csv')
    else:
        JOURNAL_VARIATIONS = pd.DataFrame([], columns=['journal', 'variation'])

    if os.path.exists('lexicon/CONFERENCE_ABBREVIATIONS.csv'):
        CONFERENCE_ABBREVIATIONS = \
            pd.read_csv('lexicon/CONFERENCE_ABBREVIATIONS.csv')
    else:
        CONFERENCE_ABBREVIATIONS = pd.DataFrame(
            [], columns=['conference', 'abbreviation'])

    return JOURNAL_ABBREVIATIONS, JOURNAL_VARIATIONS, CONFERENCE_ABBREVIATIONS


def retrieve_crowd_resources():

    JOURNAL_ABBREVIATIONS = pd.DataFrame(
        [], columns=['journal', 'abbreviation'])
    JOURNAL_VARIATIONS = pd.DataFrame([], columns=['journal', 'variation'])
    CONFERENCE_ABBREVIATIONS = pd.DataFrame(
        [], columns=['conference', 'abbreviation'])

    for resource in [x for x in os.listdir() if 'crowd_resource_' == x[:15]]:

        JOURNAL_ABBREVIATIONS_ADD = pd.read_csv(
            resource + '/lexicon/JOURNAL_ABBREVIATIONS.csv')
        JOURNAL_ABBREVIATIONS = pd.concat([JOURNAL_ABBREVIATIONS,
                                           JOURNAL_ABBREVIATIONS_ADD])

        JOURNAL_VARIATIONS_ADD = pd.read_csv(
            resource + '/lexicon/JOURNAL_VARIATIONS.csv')
        JOURNAL_VARIATIONS = pd.concat([JOURNAL_VARIATIONS,
                                        JOURNAL_VARIATIONS_ADD])

        CONFERENCE_ABBREVIATIONS_ADD = pd.read_csv(
            resource + '/lexicon/CONFERENCE_ABBREVIATIONS.csv')
        CONFERENCE_ABBREVIATIONS = pd.concat([CONFERENCE_ABBREVIATIONS,
                                              CONFERENCE_ABBREVIATIONS_ADD])

    return JOURNAL_ABBREVIATIONS, JOURNAL_VARIATIONS, CONFERENCE_ABBREVIATIONS


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
    try:
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        wo_ac = [
            rmdiacritics(c)
            for c in nfkd_form if not unicodedata.combining(c)
        ]
        wo_ac = ''.join(wo_ac)
    except ValueError:
        wo_ac = input_str
        pass
    return wo_ac


class CitationKeyPropagationError(Exception):
    pass


class HashFunctionError(Exception):
    pass


def propagated_citation_key(citation_key):

    propagated = False

    if os.path.exists(SCREEN):
        screen = pd.read_csv(SCREEN, dtype=str)
        if citation_key in screen['citation_key'].tolist():
            propagated = True

    if os.path.exists(DATA):
        # Note: this may be redundant, but just to be sure:
        data = pd.read_csv(DATA, dtype=str)
        if citation_key in data['citation_key'].tolist():
            propagated = True

    # TODO: also check data_pages?

    return propagated


def generate_citation_key(entry, bib_database=None,
                          entry_in_bib_db=False,
                          raise_error=True):
    if bib_database is not None:
        citation_key_blacklist = [entry['ID']
                                  for entry in bib_database.entries]
    else:
        citation_key_blacklist = None
    citation_key = generate_citation_key_blacklist(entry,
                                                   citation_key_blacklist,
                                                   entry_in_bib_db,
                                                   raise_error)
    return citation_key


def generate_citation_key_blacklist(entry, citation_key_blacklist=None,
                                    entry_in_bib_db=False,
                                    raise_error=True):

    # Make sure that citation_keys that have been propagated to the
    # screen or data will not be replaced
    # (this would break the chain of evidence)
    if raise_error:
        if propagated_citation_key(entry['ID']):
            raise CitationKeyPropagationError(
                'WARNING: do not change citation_keys that have been ',
                'propagated to ' + SCREEN + ' and/or ' + DATA + ' (' +
                entry['ID'] + ')',
            )

    if 'author' in entry:
        author = format_author_field(entry['author'])
    else:
        author = ''

    temp_flag = ''
    # if 'needs_manual_preparation' in entry['status']:
    #     temp_flag = '_temp_'
    if ',' in author:
        temp_citation_key = author\
            .split(',')[0].replace(' ', '') +\
            str(entry.get('year', '')) +\
            temp_flag
    else:
        temp_citation_key = author\
            .split(' ')[0] +\
            str(entry.get('year', '')) +\
            temp_flag

    if temp_citation_key.isupper():
        temp_citation_key = temp_citation_key.capitalize()
    # Replace special characters
    # (because citation_keys may be used as file names)
    temp_citation_key = remove_accents(temp_citation_key)
    temp_citation_key = re.sub(r'\(.*\)', '', temp_citation_key)
    temp_citation_key = re.sub('[^0-9a-zA-Z]+', '', temp_citation_key)

    if citation_key_blacklist is not None:
        if entry_in_bib_db:
            # allow IDs to remain the same.
            other_ids = citation_key_blacklist
            # Note: only remove it once. It needs to change when there are
            # other entries with the same ID
            if entry['ID'] in other_ids:
                other_ids.remove(entry['ID'])
        else:
            # ID can remain the same, but it has to change
            # if it is already in bib_database
            other_ids = citation_key_blacklist

        letters = iter(ascii_lowercase)
        while temp_citation_key in other_ids:
            try:
                next_letter = next(letters)
                if next_letter == 'a':
                    temp_citation_key = temp_citation_key + next_letter
                else:
                    temp_citation_key = temp_citation_key[:-1] + next_letter
            except StopIteration:
                letters = iter(ascii_lowercase)
                pass

    return temp_citation_key


def mostly_upper_case(input_string):
    # also in repo_setup.py - consider updating it separately
    if not re.match(r'[a-zA-Z]+', input_string):
        return input_string
    input_string = input_string.replace('.', '').replace(',', '')
    words = input_string.split()
    return sum(word.isupper() for word in words)/len(words) > 0.8


def title_if_mostly_upper_case(input_string):
    if not re.match(r'[a-zA-Z]+', input_string):
        return input_string
    words = input_string.split()
    if sum(word.isupper() for word in words)/len(words) > 0.8:
        return input_string.capitalize()
    else:
        return input_string


def format_author_field(input_string):
    # also in repo_setup.py - consider updating it separately

    # DBLP appends identifiers to non-unique authors
    input_string = input_string.replace('\n', ' ')
    input_string = str(re.sub(r'[0-9]{4}', '', input_string))

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


def unify_pages_field(input_string):
    # also in repo_setup.py - consider updating it separately
    if not isinstance(input_string, str):
        return input_string
    if not re.match(r'^\d*--\d*$', input_string) and '--' not in input_string:
        input_string = input_string\
            .replace('-', '--')\
            .replace('–', '--')\
            .replace('----', '--')\
            .replace(' -- ', '--')\
            .rstrip('.')

    if not re.match(r'^\d*$', input_string) and \
       not re.match(r'^\d*--\d*$', input_string) and\
       not re.match(r'^[xivXIV]*--[xivXIV]*$', input_string):
        print(f'Unusual pages: {input_string}')
    return input_string


def validate_search_details():

    search_details = pd.read_csv(SEARCH_DETAILS)

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
    if os.path.exists(SEARCH_DETAILS):
        search_details = pd.read_csv(SEARCH_DETAILS)
        try:
            records_expected = search_details.loc[
                search_details['filename'] == Path(
                    filename,
                ).name
            ].number_records.item()
            with open(filename) as bibtex_file:
                bib_database = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=False,
                    common_strings=True,
                ).parse_file(bibtex_file, partial=True)

            if len(bib_database.entries) != records_expected:
                print(
                    'Error while loading the file: number of records ',
                    'imported not identical to ',
                    'search/search_details.csv$number_records',
                )
                print(f'Loaded: {len(bib_database.entries)}')
                print(f'Expected: {records_expected}')
                return False
        except ValueError:
            # print(
            #     'WARNING: no details on ',
            #     os.path.basename(filename),
            #     ' provided in ' + SEARCH_DETAILS,
            # )
            pass
    return True


def load_references_bib(modification_check=True, initialize=False):

    if os.path.exists(os.path.join(os.getcwd(), MAIN_REFERENCES)):
        if modification_check:
            git_modification_check(MAIN_REFERENCES)
        with open(MAIN_REFERENCES) as target_db:
            references_bib = BibTexParser(
                customization=convert_to_unicode,
                ignore_nonstandard_types=False,
                common_strings=True,
            ).parse_file(target_db, partial=True)
    else:
        if initialize:
            references_bib = BibDatabase()
        else:
            print(f'{MAIN_REFERENCES} does not exist')
            sys.exit()

    return references_bib


def git_modification_check(filename):
    repo = Repo()
    index = repo.index
    if filename in [entry.a_path for entry in index.diff(None)]:
        print(
            f'WARNING: There are changes in {filename}',
            ' that are not yet added to the git index. ',
            'They may be overwritten by this script. ',
            f'Please consider to MANUALLY add the {filename}',
            ' to the index before executing script.',
        )
        if 'y' != input('override changes (y/n)?'):
            sys.exit()
    return


def get_bib_files():
    bib_files = []
    search_dir = os.path.join(os.getcwd(), 'search/')
    bib_files = [os.path.join(search_dir, x)
                 for x in os.listdir(search_dir) if x.endswith('.bib')]
    return bib_files


def get_search_files():
    supported_extensions = ['ris', 'bib', 'end',
                            'txt', 'csv', 'txt',
                            'xlsx', 'pdf']
    files = []
    search_dir = os.path.join(os.getcwd(), 'search/')
    files = [os.path.join(search_dir, x)
             for x in os.listdir(search_dir)
             if any(x.endswith(ext) for ext in supported_extensions)
             and not 'search_details.csv' == os.path.basename(x)]
    return files


def save_bib_file(bib_database, target_file=None):

    if target_file is None:
        target_file = MAIN_REFERENCES

    writer = BibTexWriter()

    writer.contents = ['entries', 'comments']
    writer.indent = '  '
    # Note: IDs should be at the beginning to facilitate git versioning
    writer.display_order = [
        'entry_link',
        'doi',
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
        'file',
    ]

    try:
        bib_database.comments.remove('% Encoding: UTF-8')
    except ValueError:
        pass

    writer.order_entries_by = ('ID', 'author', 'year')
    writer.add_trailing_comma = True
    writer.align_values = True
    bibtex_str = bibtexparser.dumps(bib_database, writer)

    with open('temp.bib', 'w') as out:
        out.write('% Encoding: UTF-8\n\n')
        out.write(bibtex_str + '\n')

    time_to_wait = 10
    time_counter = 0
    while not os.path.exists('temp.bib'):
        time.sleep(0.1)
        time_counter += 0.1
        if time_counter > time_to_wait:
            break

    if os.path.exists(target_file):
        os.remove(target_file)

    os.rename('temp.bib', target_file)

    return


def get_pdfs_of_included_papers():

    assert os.path.exists(MAIN_REFERENCES)
    assert os.path.exists(SCREEN)

    screen = pd.read_csv(SCREEN, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    pdfs = []
    for record_id in screen['citation_key'].tolist():

        with open(MAIN_REFERENCES) as bib_file:
            bib_database = BibTexParser(
                customization=convert_to_unicode,
                ignore_nonstandard_types=False,
                common_strings=True,
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
                                f'{entry["file"]} ({entry["ID"]})',
                            )

    return pdfs


def require_clean_repo(repo=None):
    if repo is None:
        repo = git.Repo('')
    if repo.is_dirty():
        print('Clean repository required (commit, discard or stash changes).')
        sys.exit()
    return True


def get_package_details():
    return 'review_template (version ' + version('review_template') + ')'


def get_version_flags():
    flag, flag_details = '', ''
    if 'dirty' in get_package_details():
        flag = ' ⚠️'
        flag_details = '\n - ⚠: created with a dirty repository version ' + \
            '(not reproducible)'
    return flag, flag_details


def build_docker_images():

    client = docker.from_env()

    repo_tags = [x.attrs.get('RepoTags', '') for x in client.images.list()]
    repo_tags = [item[:item.find(':')]
                 for sublist in repo_tags for item in sublist]

    if 'bibutils' not in repo_tags:
        print('Building bibutils Docker image...')
        filedata = pkgutil.get_data(__name__, '../docker/bibutils/Dockerfile')
        fileobj = io.BytesIO(filedata)
        client.images.build(fileobj=fileobj, tag='bibutils:latest')
    if 'lfoppiano/grobid' not in repo_tags:
        print('Pulling grobid Docker image...')
        client.images.pull('lfoppiano/grobid:0.7.0')
    if 'pandoc/ubuntu-latex' not in repo_tags:
        print('Pulling v image...')
        client.images.pull('pandoc/ubuntu-latex:2.14')

    # jbarlow83/ocrmypdf

    return
