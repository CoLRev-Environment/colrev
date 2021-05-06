#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
import os

import utils

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Reformat bibliography')
    
    bibfilename = 'data/references.bib'
    assert os.path.exists(bibfilename)

    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(common_strings=True).parse_file(bibtex_file, partial=True)
    
    utils.save_bib_file(bib_database, bibfilename)
