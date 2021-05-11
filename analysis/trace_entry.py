#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
import utils

if __name__ == "__main__":

    print('')
    print('')    
    
    print('Trace an entry')
    
    entry_string = input('provide entry in BibTeX format (all in one line, replacing \n newlines)')
    
    # entry_string = "@book{RN507,   author = {Abdalla Mikhaeil, Christine and Baskerville, Richard},  title = {An Identity Driven Escalation of Commitment to Negative Spillovers},   series = {ICIS 2017 Proceedings},  url = {https://aisel.aisnet.org/icis2017/IT-and-Social/Presentations/12}, year = {2017},type = {Book}}"

    entry_database = bibtexparser.loads(entry_string)

    bib_database = utils.load_references_bib(modification_check = True, initialize = False)
    
    nr_found = 0

    for entry in entry_database.entries:
        hash_id = utils.create_hash(entry)

        found = False
        for entry in bib_database.entries:
            if entry['hash_id'] == hash_id:
                print('citation_key: ' + entry['ID'] + ' for hash_id ' + entry['hash_id'])
                print()
                # print('') # if cleansed (hash_id in data/search/bib_details): add note: quality cleansed entry:
                print(entry)
                found = True
        if not found:
            print('Did not find entry')
