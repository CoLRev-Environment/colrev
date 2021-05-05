#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import os
import logging
import pandas as pd

import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0


def merge_duplicates(bib_database):
    
    deduplicated_bib_database = BibDatabase()
    for current_entry in bib_database.entries:
        if 0 == len(deduplicated_bib_database.entries):
            deduplicated_bib_database.entries.append(current_entry)
            continue
        # NOTE: append non-duplicated entries to deduplicated_bib_database
#        for entry in bib_database.entries:
#            if current_entry == entry:
#                continue
#            if current_entry['hash_id'] == entry['hash_id']:
        deduplicated_bib_database.entries.append(current_entry)

    return deduplicated_bib_database 

if __name__ == "__main__":

    print('')
    print('')    
    
    print('Merge duplicates')
    
    target_file = 'data/references.bib'
    temp_file = 'data/references_temp.bib'
    assert os.path.exists(target_file)
    os.rename(target_file, temp_file)

    with open(temp_file, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        
    nr_current_entries = len(bib_database.entries)

    print(str(nr_current_entries) + ' records in references.bib')
    bib_database = merge_duplicates(bib_database)

    utils.save_bib_file(bib_database, target_file)

    duplicates_removed = nr_current_entries - len(bib_database.entries)
    print('Duplicates removed: ' + str(duplicates_removed))
    print('')
