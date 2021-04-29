#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import os
import re
import logging
import csv
import pandas as pd

from string import ascii_lowercase

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0


def generate_screen_csv(screen_filename, bibfilename):
    global nr_entries_added
    
    with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)

    data = []

    for entry in bp.get_entry_list():
        nr_entries_added = nr_entries_added + 1

        data.append([entry.get("ID", "no id"),
                     entry.get("author", "no author"),
                     entry.get("title", "no title"),
                     entry.get("year", "no year"),
                     entry.get("journal", entry.get("booktitle", "no journal/booktitle")),
                     entry.get("volume", "no volume"),
                     entry.get("number", "no issue"),
                     entry.get("pages", "no pages"),
                     entry.get("doi", "no doi"),
                     entry.get("file", "no file"),
                     'TODO',  # inclusion_1
                     'TODO']) # inclusion_2
    
    screen = pd.DataFrame(data, columns=["citation_key",
                                "author",
                                "title",
                                "year",
                                "journal",
                                "volume",
                                "issue",
                                "pages",
                                "doi",
                                "file_name",
                                "inclusion_1",
                                "inclusion_2"])

    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(screen_filename, index=False, quoting=csv.QUOTE_ALL)
    
    bibtex_file.close()

    return


def update_screen_csv(screen_filename, bibfilename):
    
    global nr_entries_added
       
    with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
    
    screen = pd.read_csv(screen_filename, dtype=str)

    for entry in bp.get_entry_list():
        # skip when already available
        if 0 < len(screen[screen['citation_key'].str.startswith(entry['ID'])]):
            continue
        # print(entry['ID'])
        
        screen = pd.concat([screen, pd.DataFrame({"citation_key":[entry['ID']],
                                                  "author":entry.get("author", "no author"),
                                                  "title":entry.get("title", "no title"),
                                                  "year":entry.get("year", "no year"),
                                                  "journal":entry.get("journal", entry.get("booktitle", "no journal/booktitle")),
                                                  "volume":entry.get("volume", "no volume"),
                                                  "issue":entry.get("number", "no issue"),
                                                  "pages":entry.get("pages", "no pages"),
                                                  "doi":entry.get("doi", "no doi"),
                                                  "file_name":entry.get("file", "no file"),
                                                  "inclusion_1":['TODO'],
                                                  "inclusion_2":['TODO']})], axis=0, ignore_index=True)
        nr_entries_added = nr_entries_added + 1

    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(screen_filename, index=False, quoting=csv.QUOTE_ALL)
    
    return
    

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Screen')
    print('TODO: validation to be implemented here')

    bibfilename = 'data/references.bib'
    screen_file = 'data/screen.csv'

    
    if not os.path.exists(screen_file):
        print('Created screen.csv')
        print('0 records in screen.csv')
        generate_screen_csv(screen_file, bibfilename)
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
