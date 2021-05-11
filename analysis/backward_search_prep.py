#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import csv
import pandas as pd

import utils

def get_included_pdfs(screen_file, bib_database):
    
    pdfs = []
    
    screen = pd.read_csv(screen_file, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    for record_id in screen['citation_key'].tolist():
        
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
    
    if not os.path.exists('data/search/backward'):
        os.mkdir('data/search/backward')
    
    bib_database = utils.load_references_bib(modification_check = True, initialize = False)

    screen_file = 'data/screen.csv'
    assert os.path.exists(screen_file)

    pdfs = get_included_pdfs(screen_file, bib_database)
    print('to check: pdf paths should start with data/pdf/')
#    pdfs = ['data/pdf/example1.pdf','data/pdf/example2.pdf']
    
    df = pd.DataFrame({"filenames" : pdfs})
    
    df.to_csv('data/search/backward_search_pdfs.csv', index=False, quoting=csv.QUOTE_ALL)