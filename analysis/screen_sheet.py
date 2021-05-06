#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.customization import convert_to_unicode

import os
import logging
import csv
import pandas as pd

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0


def generate_screen_csv(screen_filename, exclusion_criteria, bibfilename):
    global nr_entries_added
    
    with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)

    data = []

    for entry in bp.get_entry_list():
        nr_entries_added = nr_entries_added + 1
        
        if not 'ID' in entry:
            print('Error: entry without citation_key in references.bib (skipping')
            continue
        
        data.append([entry['ID'],
                     'TODO',
                     'TODO'] + ['TODO']*len(exclusion_criteria) + [''])
    
    screen = pd.DataFrame(data, columns=["citation_key",
                                "inclusion_1",
                                "inclusion_2"] + exclusion_criteria + ['comment'])

    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(screen_filename, index=False, quoting=csv.QUOTE_ALL)
    
    bibtex_file.close()

    return

def update_screen_csv(screen_filename, bibfilename):
    
    global nr_entries_added
       
    with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
    
    bibliography_file = pd.DataFrame.from_dict(bp.entries)
    screen = pd.read_csv(screen_filename, dtype=str)
    
    papers_to_screen = bibliography_file['ID'].tolist()
    screened_papers = screen['citation_key'].tolist()
    
    papers_no_longer_in_search = [x for x in screened_papers if x not in papers_to_screen]
    if len(papers_no_longer_in_search) > 0:
        print('WARNING: papers in screen.csv are no longer in search (references.bib): [' + ', '.join(papers_no_longer_in_search) + ']')
        print('note: check and remove the citation_keys/rows from screen.csv')
    
    for paper_to_screen in papers_to_screen:
        if paper_to_screen not in screened_papers:
            add_entry = pd.DataFrame({"citation_key":[paper_to_screen],
                                                  "inclusion_1":['TODO'],
                                                  "inclusion_2":['TODO']})
            add_entry = add_entry.reindex(columns=screen.columns, fill_value='TODO')
            add_entry['comment'] = ''
    
            screen = pd.concat([screen, add_entry], axis=0, ignore_index=True)
            nr_entries_added = nr_entries_added + 1

    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(screen_filename, index=False, quoting=csv.QUOTE_ALL, na_rep='NA')
    
    return
    

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Screen')
    print('TODO: validation to be implemented here')

    bibfilename = 'data/references.bib'
    screen_file = 'data/screen.csv'

    
    if not os.path.exists(screen_file):
        print('Creating screen.csv')
        exclusion_criteria = input('Please provide a list of exclusion criteria [criterion1,criterion2,...]: ')        
        
        if exclusion_criteria == '':
            exclusion_criteria = []
        else:
            exclusion_criteria = exclusion_criteria.strip('[]').replace(' ','_').split(',')
            exclusion_criteria = ['ec_' + criterion for criterion in exclusion_criteria]
 
       # Exclusion criteria should be unique
        assert len(exclusion_criteria) == len(set(exclusion_criteria))

        generate_screen_csv(screen_file, exclusion_criteria, bibfilename)
        print('Created screen.csv')
        print('0 records in screen.csv')
    else:
        print('Loaded existing screen.csv')
        file = open(screen_file)
        reader = csv.reader(file)
        lines= len(list(reader))-1
        print(str(lines) + ' records in screen.csv')

        update_screen_csv(screen_file, bibfilename)

    print(str(nr_entries_added) + ' records added to screen.csv')
    file = open(screen_file)
    reader = csv.reader(file)
    lines= len(list(reader))-1
    print(str(lines) + ' records in screen.csv')
    print('')
