#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.customization import convert_to_unicode

import logging

import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

def trace_hash(bibfilename, hash_id_needed):
    global nr_found
    
    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        
        for entry in bib_database.entries:
            if utils.create_hash(entry) == hash_id_needed:
                print('\n\n Found hash ' + hash_id_needed + '\n in ' + bibfilename + '\n\n')
                print(entry)
                nr_found += 1
    return

if __name__ == "__main__":

    print('')
    print('')    
    
    print('Trace hash_id')

    hash_id_needed = input('provide hash_id')

    nr_found = 0

    for bib_file in utils.get_bib_files():
        trace_hash(bib_file, hash_id_needed)
    
    if nr_found == 0:
        print('Did not find hash_id')
