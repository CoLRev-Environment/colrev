#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import re
import os
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode
import pandas as pd
import sys
from git import Repo

def robust_append(string_to_hash, to_append):
    
    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub('\s+',' ', to_append)
    to_append = to_append.lower()
    
    string_to_hash = string_to_hash + to_append
    
    return string_to_hash

def create_hash(entry):
    string_to_hash = robust_append('', entry.get("author", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("year", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("title", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("journal", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("booktitle", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("volume", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("issue", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("pages", ""))

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()


def validate_search_details():
    
    search_details = pd.read_csv('data/search/search_details.csv')
    
    # check columns
    predef_colnames = {'filename', 'number_records', 'iteration', 'date_start', 'date_completion', 'source_url', 'search_parameters', 'responsible', 'comment'}
    if not set(search_details.columns) == predef_colnames:
        print('Problem: columns in data/search/search_details.csv not matching predefined colnames')
        print(set(search_details.columns))
        print('Should be')
        print(predef_colnames)
        print('')
        sys.exit()
    
    # TODO: filenames should exist, all files should have a row, iteration, number_records should be int, start
    
    return

def validate_bib_file(filename):
    
    # Do not load/warn when bib-file contains the field "Early Access Date"
    # https://github.com/sciunto-org/python-bibtexparser/issues/230
    
    with open(filename) as bibfile:
        if 'Early Access Date' in bibfile.read():
            print('Error while loading the file: replace Early Access Date in bibfile before loading!')
            return False

    # check number_records matching search_details.csv    
    search_details = pd.read_csv('data/search/search_details.csv')
    try:
        records_expected = search_details.loc['data/search/' + search_details['filename'] == filename].number_records.item()
        with open(filename, 'r') as bibtex_file:
            bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        
        if len(bib_database.entries) != records_expected:
            print('Error while loading the file: number of records imported not identical to data/search/search_details.csv$number_records')
            print('Loaded: ' + str(len(bib_database.entries)))
            print('Expected: ' + str(records_expected))
            return False
    except ValueError:
        print('WARNING: no details on ' + filename + ' provided in data/search/search_details.csv')
        pass
    return True


def load_references_bib(modification_check = True, initialize = False):
    
    references_bib_path = 'data/references.bib'
    if os.path.exists(os.path.join(os.getcwd(), references_bib_path)):
        if modification_check:
            git_modification_check('references.bib')
        with open(references_bib_path, 'r') as target_db:
            references_bib = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(target_db, partial=True)
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
        print('WARNING: There are changes in ' + filename + ' that are not yet added to the git index. They may be overwritten by this script. Please consider to MANUALLY add the ' + filename + ' to the index before executing script.')
        if 'y' != input('override changes (y/n)?'):
            sys.exit()
    
    return

def get_bib_files():
    bib_files = []

    for (dirpath, dirnames, filenames) in os.walk(os.path.join(os.getcwd(), 'data/search/')):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename).replace('/opt/workdir/','')
            if file_path.endswith('.bib'):
                if not validate_bib_file(file_path):
                    continue
                bib_files = bib_files + [file_path]
    return bib_files

def save_bib_file(bib_database, target_file):
    
    for entry in bib_database.entries:
        if entry['ENTRYTYPE'] == 'article':
            entry['ENTRYTYPE'] = 'Article'
        if entry['ENTRYTYPE'] == 'book':
            entry['ENTRYTYPE'] = 'Book'
        if entry['ENTRYTYPE'] == 'inproceedings':
            entry['ENTRYTYPE'] = 'InProceedings'
    writer = BibTexWriter()
    if bib_database.comments == []:
        bib_database.comments = ['jabref-meta: databaseType:bibtex;']
    else:
        try:
            bib_database.comments.remove('% Encoding: UTF-8')
        except ValueError:
            pass
    writer.contents = ['entries', 'comments']
    writer.indent = '  '
    # The order should match JabRefs ordering of fields used when saving a file
    writer.display_order = ['author', 'booktitle', 'journal', 'title', 'year', 'editor', 'number', 'pages', 'series', 'volume', 'abstract', 'book-author', 'book-group-author', 'doi', 'file', 'hash_id']
    # to test this order, run merge_duplicates, add version in git, edit in JabRef and inspect differences
    # There seem to be dependencies in the save order (e.g., the pages are saved in a different position by JabRef if it is a book or an article)
    # the sort order seems to be a problem when @Books have both a title and a booktitle
    writer.order_entries_by = ('ID', 'author', 'year')
    writer.add_trailing_comma = True
    writer.align_values = True
    bibtex_str = bibtexparser.dumps(bib_database, writer)
    
    with open(target_file, 'w') as out:
        out.write(bibtex_str + '\n')


    # The following fixes the formatting to prevent JabRef from introducing format changes (there may be a more elegant way to achieve this)
    os.rename('data/references.bib', 'data/references_temp_2.bib')
    
    with open('data/references_temp_2.bib', 'r') as reader:
        lines = reader.readlines()
    
    with open('data/references.bib', 'w') as writer:
        writer.write('% Encoding: UTF-8\n\n')

        max_key_length = 0
        book = False
        saved_booktitle = ''
        saved_pages = ''
        for line in lines:
            
            # Note: padding depends on the longest field/key in each entry...
            if line[0] == '@':
                citation_key = line[line.find('{')+1:-2]
                # get longest key
                max_key_length = 0
                for entry in bib_database.entries:
                    if entry['ID'] == citation_key:
                        for key in entry.keys():
                            if 'ENTRYTYPE' == key: 
                                continue
                            if len(key) > max_key_length:
                                max_key_length = len(key)
                        break
                shorten = (18-max_key_length)*' ' + '='
                if line[0:6] == '@Book{':
                    book = True
                else:
                    book = False
                saved_booktitle = ''
                saved_pages = ''
            if max_key_length != 0:
                line = line.replace(shorten,' =')
            

            if book:
                if 'booktitle ' in line:
                    saved_booktitle = line
                    continue
                if 'pages ' in line:
                    saved_pages = line
                    continue

            writer.write(line)
            
            if book and 'year ' in line:
                writer.write (saved_booktitle)
            if book and 'hash_id ' in line:
                writer.write (saved_pages)

    # writer.write('@Comment{jabref-meta: databaseType:bibtex;}\n')

    os.remove('data/references_temp_2.bib')
    return