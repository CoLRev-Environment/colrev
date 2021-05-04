#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.customization import convert_to_unicode

import os
import pandas as pd


def get_included_pdfs(screen_file, bibtex_file):
    
    pdfs = []
    
    screen = pd.read_csv(screen_file, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    for record_id in screen['citation_key'].tolist():
        
        with open(bibtex_file, 'r') as bib_file:
            bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(bib_file, partial=True)
            
            for entry in bib_database.entries:
                if entry.get('ID', '') == record_id:
                    if 'file' in entry:
                        if os.path.exists(entry['file']):
                            pdfs.append(entry['file'])
                        else:
                            print('- Error: file not available ' + entry['file'] + ' (' + entry['ID'] + ')')

    return pdfs

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Backward search - prep')
    
    bibtex_file = 'data/references.bib'
    assert os.path.exists(bibtex_file)

    screen_file = 'data/screen.csv'
    assert os.path.exists(screen_file)

    pdfs = get_included_pdfs(screen_file, bibtex_file)
    
    print('TODO: remove the following and test')
    pdfs= ['data/pdfs/example1.pdf', 'data/pdfs/example2.pdf']
    
    df = pd.DataFrame({"filenames" : pdfs})
    
    df.to_csv('data/search/backward_search_pdfs.csv', index=False)