#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
import csv
import os
import re
from fuzzywuzzy import fuzz
import pandas as pd
from tqdm import tqdm


def get_similarity(df_a, df_b):
    if 'author' in df_a and 'author' in df_b:
        authors_a = re.sub(r'[^A-Za-z0-9, ]+', '', str(df_a['author']).lower())
        authors_b = re.sub(r'[^A-Za-z0-9, ]+', '', str(df_b['author']).lower())
        author_similarity = fuzz.ratio(authors_a, authors_b)/100
    else:
        author_similarity = 1 # TBD - unknown?

    #partial ratio (catching 2010-10 or 2001-2002)
    if 'year' in df_a and 'year' in df_b:
        year_similarity = fuzz.partial_ratio(str(df_a['year']), str(df_b['year']))/100
    else:
        year_similarity = 1  # TBD - unknown?

    if 'journal' in df_a and 'journal' in df_b:
        journal_a = re.sub(r'[^A-Za-z0-9 ]+', '', str(df_a['journal']).lower())
        journal_b = re.sub(r'[^A-Za-z0-9 ]+', '', str(df_b['journal']).lower())
        
        #TODO: replacing abbreviations before matching and matching lower cases (catching different citation styles)
        # for i, row in JOURNAL_ABBREVIATIONS.iterrows():
        #     if journal_a == row['abbreviation']:
        #         journal_a = row['journal']
        #     if journal_b == row['abbreviation']:
        #         journal_b = row['journal']
        journal_similarity = fuzz.ratio(journal_a, journal_b)/100
    else:
        journal_similarity = 1  # TBD - unknown?

    if 'title' in df_a and 'title' in df_b:    
        title_a = re.sub(r'[^A-Za-z0-9, ]+', '', str(df_a['title']).lower())
        title_b = re.sub(r'[^A-Za-z0-9, ]+', '', str(df_b['title']).lower())
        title_similarity = fuzz.ratio(title_a, title_b)/100
    else:
        title_similarity = 1  # TBD - unknown?

    weights = [0.15, 0.75, 0.05, 0.05]
    similarities = [author_similarity, title_similarity, year_similarity, journal_similarity]
    weighted_average = sum(similarities[g] * weights[g] for g in range(len(similarities)))

    return weighted_average

def get_duplication_probability(entry, bibliography_file):
    pd.set_option('mode.chained_assignment', None)
    bibliography_file['similarity'] = 0
    for i, r in bibliography_file.iterrows():
        bibliography_file.loc[i, 'similarity'] = get_similarity(r, entry)

    # do not consider the duplication probabiliy of the entry with itself
    bibliography_file.loc[bibliography_file['hash_id'] == entry['hash_id'], 'similarity'] = 0 

    max_similarity = bibliography_file['similarity'].max()
    # corresponding entry: bibliography_file.loc[bibliography_file['similarity'].idxmax()]

    return max_similarity

def pre_merging_quality_check(bibfilename):
    
    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(common_strings=True).parse_file(bibtex_file, partial=True)
        
        bibliography_file = pd.DataFrame.from_dict(bib_database.entries)
        
        for entry in tqdm(bib_database.entries):
            
            if 'article' == entry['ENTRYTYPE']:
                required_fields = ["author", "year", "title", "journal", "volume", "issue", "number", "pages"]
            elif 'inproceedings' == entry['ENTRYTYPE']:
                required_fields = ["author", "year", "title", "booktitle"]
            else:
                required_fields = ["author", "year", "title"]

            nr_available_fields = 0
            
            for key in entry.keys():
                if key in required_fields:
                    nr_available_fields += 1
            
            # note: required field needs
            completeness = nr_available_fields/(len(required_fields))
            entry['completeness'] = completeness

            duplication_probability = get_duplication_probability(entry, bibliography_file)
            # possibly also return the most likely match?
            entry['duplication_probability'] = duplication_probability


        bib_file = pd.DataFrame.from_dict(bib_database.entries)
        bib_file.to_csv('data/references_pre_screen_quality_check.csv', index=False, quoting=csv.QUOTE_ALL)
    return

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Pre-merging quality check')
    
    bib_database = 'data/references.bib'
    assert os.path.exists(bib_database)

    JOURNAL_ABBREVIATIONS = pd.read_csv('analysis/JOURNAL_ABBREVIATIONS.csv')
    pre_merging_quality_check(bib_database)
