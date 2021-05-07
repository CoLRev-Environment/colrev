#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import os
import sys
import logging
import pandas as pd
from string import ascii_lowercase

import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0
nr_duplicates_hash_ids = 0

def gather(bibfilename, combined_bib_database):
    global nr_entries_added 
    global nr_duplicates_hash_ids
    
    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        
        for entry in bib_database.entries:
             
            entry['hash_id'] = utils.create_hash(entry)

            if('abstract' in entry): entry['abstract'] = entry['abstract'].replace('\n', ' ')
            if('author' in entry): entry['author'] = entry['author'].replace('\n', ' ')
            if('title' in entry): entry['title'] = entry['title'].replace('\n', ' ')
            if('booktitle' in entry): entry['booktitle'] = entry['booktitle'].replace('\n', ' ')
            if('doi' in entry): entry['doi'] = entry['doi'].replace('http://dx.doi.org/', '')
            if('pages' in entry): 
                if 1 == entry['pages'].count('-'):
                    entry['pages'] = entry['pages'].replace('-', '--')
            
            
            fields_to_keep = ["ID", "hash_id", "ENTRYTYPE", "author", "year", "title", "journal", "booktitle", "series", "volume", "issue", "number", "pages", "doi", "abstract", "editor", "book-group-author", "book-author", "keywords"]
            fields_to_drop = ["type", "url", "organization", "issn", "isbn", "note", "unique-id", "month", "researcherid-numbers", "orcid-numbers", "eissn", "article-number"]
            for val in list(entry):
                if(val not in fields_to_keep):
                    # drop all fields not in fields_to_keep
                    entry.pop(val)
                    # but warn if fields are dropped that are not in the typical fields_to_drop
                    if not val in fields_to_drop:
                        print('  dropped ' + val + ' field')
            
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
    utils.validate_search_details()
    
    target_file = 'data/references.bib'

    if os.path.exists(os.path.join(os.getcwd(), target_file)):
        with open(target_file, 'r') as target_db:
            print('Loading existing references.bib')
            combined_bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(target_db, partial=True)
    else:
        print('Created references.bib.')
        combined_bib_database = BibDatabase()
        if os.path.exists('data/search/bib_details.csv'):
            os.remove('data/search/bib_details.csv')

    nr_current_entries = len(combined_bib_database.entries)

    # TODO: define preferences (start by processing e.g., WoS, then GS) or use heuristics to start with the highest quality (most complete) entries first.

    search_details = pd.read_csv('data/search/search_details.csv')

    print(str(nr_current_entries) + ' records in references.bib')
    for bib_file in utils.get_bib_files():
        print('Loading ' + bib_file) 
        combined_bib_database = gather(bib_file, combined_bib_database)

    utils.save_bib_file(combined_bib_database, target_file)

    if nr_duplicates_hash_ids > 0:
           print(str(nr_duplicates_hash_ids) + ' duplicate records identified due to identical hash_ids')
    print(str(nr_entries_added) + ' records added to references.bib')
    print(str(len(combined_bib_database.entries)) + ' records in references.bib')
    print('')
