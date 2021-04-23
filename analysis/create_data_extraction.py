#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import os
import re
import logging
import hashlib
import csv

from string import ascii_lowercase

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

def write_csv_line(wr, entry):
    # print(entry)
    row = []
    citation_key = entry.get("ID", "no id")
    row.append(citation_key)
    author = entry.get("author", "no author")
    row.append(author)
    title = entry.get("title", "no title")
    row.append(title)
    year = entry.get("year", "no year")
    row.append(year)
    journal = entry.get("journal", "no journal")
    booktitle = entry.get("booktitle", "no booktitle")
    if journal == "no journal" and booktitle != "no booktitle":
        journal = booktitle
    row.append(journal)
    volume = entry.get("volume", "no volume")
    row.append(volume)
    issue = entry.get("number", "no issue")
    row.append(issue)
    pages = entry.get("pages", "no pages")
    row.append(pages)
    doi = entry.get("doi", "no doi")
    row.append(doi)
    file_name = entry.get("file", "no file")
    row.append(file_name)
    row.append('TODO') # inclusion_1
    row.append('TODO') # inclusion_2

    wr.writerow(row)
    return

def generate_data_extraction_csv(data_extraction_file, screen_file):
    csv_file = open(data_extraction_file, 'w', encoding='utf-8', newline='')
    wr = csv.writer(csv_file, quoting=csv.QUOTE_ALL)

    with open(screen_file, newline='') as screen_file:
        csv_reader = csv.reader(screen_file)

        wr.writerow(["citation_key",
                                "author",
                                "title",
                                "year",
                                "journal",
                                "volume",
                                "issue",
                                "pages",
                                "doi",
                                "file_name",
                                "data_1"])
    
        for row in csv_reader:
            if row[11] == 'inclusion_2':
                continue
            if row[11] == 'yes':
                row = row[:10]
                row.append('TODO')
                wr.writerow(row)
 
    csv_file.close()
    return


def update_data_extraction_csv(screen_filename, screen_file_prior, bibfilename):
    
    # TODO (cf. update_screen.py/update_screen_csv(...))
    
    return

if __name__ == "__main__":
    
    screen_file = 'data/screen.csv'
    data_extraction_file = 'data/data.csv'

    generate_data_extraction_csv(data_extraction_file, screen_file)

#    if not os.path.exists(data_extraction_file):
#        generate_data_extraction_csv(data_extraction_file, screen_file)
#    else:
#        os.rename(data_extraction_file, 'data/data_prior.csv')
#        update_data_extraction_csv(data_extraction_file, 'data/data_prior.csv', screen_file)
#        os.remove('data/data_prior.csv')

