#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import os
import re
import sys
import logging
import pandas as pd

import utils

from string import ascii_lowercase

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_duplicates_hash_ids = 0
nr_entries_added = 0
nr_current_entries = 0

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
    print('TODO: further checks to be implemented here')
    
    return

def validate_bib_file(filename):
    
    # Do not load/warn when bib-file contains the field "Early Access Date"
    # https://github.com/sciunto-org/python-bibtexparser/issues/230
    
    with open(os.path.join('data/search/', filename)) as bibfile:
        if 'Early Access Date' in bibfile.read():
            print('Error while loading the file: replace Early Access Date in bibfile before loading!')
            return False

    
    # check number_records matching search_details.csv    
    search_details = pd.read_csv('data/search/search_details.csv')
    records_expected = search_details.loc[search_details['filename'] == filename].number_records.item()
    with open(os.path.join('data/search/', filename), 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
    
    if len(bib_database.entries) != records_expected:
        print('Error while loading the file: number of records imported not identical to data/search/search_details.csv$number_records')
        print('Loaded: ' + str(len(bib_database.entries)))
        print('Expected: ' + str(records_expected))
        return False
    
    return True

def gather(bibfilename, combined_bib_database):
    global nr_entries_added 
    global nr_duplicates_hash_ids

    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        
        for entry in bib_database.entries:
            
            entry['hash_id'] = utils.create_hash(entry)
            
            entry['ID'] = entry.get('author', '').split(' ')[0].capitalize() + entry.get('year', '')
            entry['ID'] = re.sub("[^0-9a-zA-Z]+", "", entry['ID'])

            if('abstract' in entry): entry['abstract'] = entry['abstract'].replace('\n', ' ')
            if('author' in entry): entry['author'] = entry['author'].replace('\n', ' ')
            if('title' in entry): entry['title'] = entry['title'].replace('\n', ' ')
            if('booktitle' in entry): entry['booktitle'] = entry['booktitle'].replace('\n', ' ')
            
            keep_fields = ["ID", "author", "year", "title", "journal", "booktitle", "volume", "issue", "pages", "doi", "abstract"]
            for val in keep_fields :
                if(val not in entry):
                    entry.pop(val)
            
        for entry in bib_database.entries:
            
            if 0 == len(combined_bib_database.entries):
                combined_bib_database.entries.append(entry)
                nr_entries_added += 1

                continue
            
            if not entry['hash_id'] in [x['hash_id'] for x in combined_bib_database.entries]: 
                
                # Make sure the ID is unique (otherwise: append letters until this is the case)
                temp_id = entry['ID']
                letters = iter(ascii_lowercase)
                while temp_id in [x['ID'] for x in combined_bib_database.entries]:
                    temp_id = entry['ID'] + next(letters)
                entry['ID'] = temp_id
                
                combined_bib_database.entries.append(entry)
                nr_entries_added += 1
            else:
                nr_duplicates_hash_ids += 1

    return combined_bib_database

if __name__ == "__main__":

    print('')
    print('')    
    
    print('Search')
    validate_search_details()
    
    target_file = 'data/references.bib'

    if os.path.exists(os.path.join(os.getcwd(), target_file)):
        with open(target_file, 'r') as target_db:
            print('Loading existing references.bib')
            combined_bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(target_db, partial=True)
    else:
        print('Created references.bib.')
        combined_bib_database = BibDatabase()

    nr_current_entries = len(combined_bib_database.entries)

    writer = BibTexWriter()

    # TODO: define preferences (start by processing e.g., WoS, then GS) or use heuristics to start with the highest quality (most complete) entries first.

    pattern_search_results= re.compile('[1-2][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]-.*bib$')

    print(str(nr_current_entries) + ' records in references.bib')
    for (dirpath, dirnames, filenames) in os.walk(os.path.join(os.getcwd(), 'data/search/')):
        for filename in filenames:
            if re.match(pattern_search_results, filename):
                print('Loading ' + filename) 
                if not validate_bib_file(filename):
                    continue
                combined_bib_database = gather(os.path.join('data/search/', filename), combined_bib_database)

    writer.contents = ['comments', 'entries']
    writer.indent = '    '
    writer.order_entries_by = ('ID', 'author', 'year')
    bibtex_str = bibtexparser.dumps(combined_bib_database, writer)
    
    with open(target_file, 'w') as out:
        out.write(bibtex_str + '\n')
    
    if nr_duplicates_hash_ids > 0:
        print(str(nr_duplicates_hash_ids) + ' duplicate records identified due to identical hash_ids')
    print(str(nr_entries_added) + ' records added to references.bib')
    print(str(len(combined_bib_database.entries)) + ' records in references.bib')
    print('')
