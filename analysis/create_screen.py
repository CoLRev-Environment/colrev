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

def generate_screen_csv(screen_filename, bibfilename):
    csv_file = open(screen_filename, 'w', encoding='utf-8', newline='')
    wr = csv.writer(csv_file, quoting=csv.QUOTE_ALL)

    with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)

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
                                "inclusion_1",
                                "inclusion_2"])
        for entry in bp.get_entry_list():
            write_csv_line(wr, entry)
            
        bibtex_file.close()

    csv_file.close()
    return


def update_screen_csv(screen_filename, screen_file_prior, bibfilename):
    
    csv_file = open(screen_filename, 'w', encoding='utf-8', newline='')
    wr = csv.writer(csv_file, quoting=csv.QUOTE_ALL)

    with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)

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
                                "inclusion_1",
                                "inclusion_2"])

        bp_entry_list = bp.get_entry_list()

        prior_csv_file = open(screen_file_prior, newline='')
        csv_reader = csv.reader(prior_csv_file)
        next_csv_entry = next(csv_reader)
        next_csv_entry = next(csv_reader)
        bp_entry_list = sorted(bp_entry_list, key=lambda entry: entry['ID'] , reverse=True)
        entry = bp_entry_list.pop()
        last_written = []
        while True:
            try:
#                This should be caught by the IndexError
#                if 0 == len(bp_entry_list):
#                    break
                next_search_id = entry.get("ID", "no id")
                assert next_search_id != 'no id'
#                print('csv ' + next_csv_entry[0])
#                print('bib ' + next_search_id)
                if next_search_id == next_csv_entry[0]:
                    wr.writerow(next_csv_entry)
                    last_written = next_csv_entry
#                    print('written identical IDs ' + next_search_id)
                    next_csv_entry = next(csv_reader)
                    if 0 == len(bp_entry_list): break
                    entry = bp_entry_list.pop()
                    next_search_id = entry.get("ID", "no id")
                    assert next_search_id != 'no id'

                else:
                    if next_search_id.lower() == min(next_search_id.lower(), next_csv_entry[0].lower()):
                        write_csv_line(wr, entry)
                        print('added ID from search ' + next_search_id)
                        if 0 == len(bp_entry_list): break
                        entry = bp_entry_list.pop()
                        next_search_id = entry.get("ID", "no id")
                        assert next_search_id != 'no id'

                    else:
                        wr.writerow(next_csv_entry)
                        last_written = next_csv_entry
                        print('ID no longer available in search ' + next_csv_entry[0])
                        next_csv_entry = next(csv_reader)                    

            except StopIteration:
                break
 
        # append remaining entries from prior_csv or from bp
        
        while True:
            try:
                if last_written == next_csv_entry:
                    break
                wr.writerow(next_csv_entry)
                print('ID no longer available in search ' + next_csv_entry[0])
                next_csv_entry = next(csv_reader)
            except StopIteration:
                break
        
        while True:
            if not bp_entry_list:
                break
            entry = bp_entry_list.pop() 
            next_search_id = entry.get("ID", "no id")
            assert next_search_id != 'no id'
            write_csv_line(wr, entry)
            print('added ID from search ' + next_search_id)

        
        bibtex_file.close()

    csv_file.close()
    
    return

if __name__ == "__main__":
    
    bibfilename = 'data/references.bib'
    screen_file = 'data/screen.csv'

    if not os.path.exists(screen_file):
        generate_screen_csv(screen_file, bibfilename)
    else:
        os.rename(screen_file, 'data/screen_prior.csv')
        update_screen_csv(screen_file, 'data/screen_prior.csv', bibfilename)
        os.remove('data/screen_prior.csv')

