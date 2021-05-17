#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
import csv
import pandas as pd

import utils

def extract_manual_pre_merging_edits(manual_bib_database, automated_bib_database):
    
    edits = []
    for manual_entry in manual_bib_database.entries:

        automated_entry = [entry for entry in automated_bib_database.entries if entry['hash_id'] == manual_entry['hash_id']][0]

#        # TODO: warn if not exists

        hash_id = manual_entry['hash_id']
        for field in manual_entry:
            if 'hash_id' == field:
                continue
            if field not in automated_entry:
                edits.append([hash_id, field,'',manual_entry[field]])
                continue
            if manual_entry[field] != automated_entry[field]:
                edits.append([hash_id, field,automated_entry[field],manual_entry[field]])
                continue


    print('TODO: if edits.csv exists, open and merge!')

    edits_df = pd.DataFrame(edits, columns =["hash_id",
                    "field",
                    "from_automated",
                    "to_manual"])

    edits_df.sort_values(by=['hash_id'], inplace=True)
    edits_df.to_csv('data/edits.csv', index=False, quoting=csv.QUOTE_ALL)

       
    return

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Extract manual pre-merging edits')
        
    # Another possibility would be to 
    # rerun  merging and cleansing to get the automated version. This would require a lot of time. We therefore save a copy at the end of cleanse_records.py
        
    bib_database = utils.load_references_bib(modification_check = True, initialize = False)

    with open('data/references_last_automated.bib', 'r') as automated_bibtex_file:
        automated_bib_database = bibtexparser.bparser.BibTexParser(common_strings=True).parse_file(automated_bibtex_file, partial=True)

    extract_manual_pre_merging_edits(bib_database, automated_bib_database)

