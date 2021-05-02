#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode

import os
import shutil
import csv
import pandas as pd

def extract_manual_pre_merging_edits(bibfilename_manual, bibfilename_automated):
    
    with open(bibfilename_manual, 'r') as manual_bibtex_file:
        manual_bib_database = bibtexparser.bparser.BibTexParser(common_strings=True).parse_file(manual_bibtex_file, partial=True)

    with open(bibfilename_automated, 'r') as automated_bibtex_file:
        automated_bib_database = bibtexparser.bparser.BibTexParser(common_strings=True).parse_file(automated_bibtex_file, partial=True)

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
    
    bibfilename = 'data/references.bib'
    assert os.path.exists(bibfilename)
    
    # Another possibility would be to 
    # rerun  merging and cleansing to get the automated version. This would require a lot of time. We therefore save a copy at the end of cleanse_records.py



    extract_manual_pre_merging_edits(bibfilename, 'data/references_last_automated.bib')


