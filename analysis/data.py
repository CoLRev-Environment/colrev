#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import os
import sys
import re
import logging
import csv
import pandas as pd

from string import ascii_lowercase

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0


def generate_data_csv(data_file, screen_filename):
    global nr_entries_added
    
    screen = pd.read_csv(screen_filename, dtype=str)
       
#    included = screen[screen['inclusion_2'] == 'yes']
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)
    
    if len(screen) == 0:
        print('no records included yet (screen.csv$inclusion_2 == yes)')
        print()
        sys.exit()
    
    screen['coding_dimension1'] = 'TODO'
    del screen['inclusion_1']
    del screen['inclusion_2']
    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(data_file, index=False, quoting=csv.QUOTE_ALL)
    
    return


def update_data_csv(data_file, screen_filename):
    
    global nr_entries_added
       
    data = pd.read_csv(data_file, dtype=str)
    screen = pd.read_csv(screen_filename, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    print('TODO: warn when records are no longer included')
    
    for record_id in screen['citation_key'].tolist():
#        # skip when already available
        if 0 < len(data[data['citation_key'].str.startswith(record_id)]):
            continue
        
        data = pd.concat([data, pd.DataFrame({"citation_key":record_id,
                                                  "coding_dimension1":['TODO']})], axis=0, ignore_index=True)
        nr_entries_added = nr_entries_added + 1

    data.sort_values(by=['citation_key'], inplace=True)
    data.to_csv(data_file, index=False, quoting=csv.QUOTE_ALL)
    
    return
    

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Data')
    print('TODO: validation to be implemented here')

    screen_file = 'data/screen.csv'
    data_file = 'data/data.csv'

    
    if not os.path.exists(data_file):
        print('Created data.csv')
        print('0 records in data.csv')
        generate_data_csv(data_file, screen_file)
    else:
        print('Loaded existing data.csv')
        file = open(data_file)
        reader = csv.reader(file)
        lines= len(list(reader))-1
        print(str(lines) + ' records in data.csv')

        update_data_csv(data_file, screen_file)

    print(str(nr_entries_added) + ' records added to data.csv')
    file = open(data_file)
    reader = csv.reader(file)
    lines= len(list(reader))-1
    print(str(lines) + ' records in data.csv')
    print('')
