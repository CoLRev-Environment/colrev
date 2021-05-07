#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import os
import logging

import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_found = 0

if __name__ == "__main__":

    print('')
    print('')    
    
    print('Trace an entry')
    
    bibfilename = 'data/references.bib'

    entry_string = input('provide entry in BibTeX format (all in one line, replacing \n newlines)')
    
    # entry_string = "@book{RN507,   author = {Abdalla Mikhaeil, Christine and Baskerville, Richard},  title = {An Identity Driven Escalation of Commitment to Negative Spillovers},   series = {ICIS 2017 Proceedings},  url = {https://aisel.aisnet.org/icis2017/IT-and-Social/Presentations/12}, year = {2017},type = {Book}}"

    bib_database = bibtexparser.loads(entry_string)
    
    for entry in bib_database.entries:
#        print(entry)
        hash_id = utils.create_hash(entry)
#        print(hash_id)

        with open(bibfilename, 'r') as bibtex_file:
            bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
                    
            found = False
            for entry in bib_database.entries:
                if entry['hash_id'] == hash_id:
                    print('citation_key: ' + entry['ID'] + ' for hash_id ' + entry['hash_id'])
                    print()
#                    print('') # if cleansed (hash_id in data/search/bib_details): add note: quality cleansed entry:
                    print(entry)
                    found = True
            if not found:
                print('Did not find entry')
