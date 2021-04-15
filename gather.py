#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

from citeproc.source.bibtex import BibTeX
from citeproc import CitationStylesStyle, CitationStylesBibliography
from citeproc import formatter
from citeproc import Citation, CitationItem

import os
import sys
import xlsxwriter
import csv
import tempfile
import logging
import hashlib

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

excel_row_index = 0

def write_row(spreadsheet, row):
    if isinstance(spreadsheet, xlsxwriter.worksheet.Worksheet):
        global excel_row_index
        column_index = 0
        for item in row:
            spreadsheet.write(excel_row_index, column_index, item)
            column_index = column_index + 1
        excel_row_index = excel_row_index + 1
    else:
        spreadsheet.writerow(row)
    return

def generate_spreadsheet(spreadsheet, bibfilename):
    with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)

        write_row(spreadsheet, ["citation_key",
                                "author",
                                "author_count",
                                "title",
                                "year",
                                "type",
                                "journal",
                                "volume",
                                "issue",
                                "pages",
                                "file_name",
                                "number-of-cited-references",
                                "times-cited",
                                "doi"])
        for entry in bp.get_entry_list():
            # print(entry)
            row = []
            citation_key = entry.get("ID", "no id")
            row.append(citation_key)
            author = entry.get("author", "no author")
            for src, target in replacements_author.items():
                author = author.replace(src, target)
            row.append(author)
            author_count = str(author.count(","))
            row.append(author_count)
            title = entry.get("title", "no title")
            for src, target in replacements_title.items():
                title = title.replace(src, target)
            row.append(title)
            year = entry.get("year", "no year")
            row.append(year)
            publication_type = entry.get("type", "no type")
            for src, target in replacements_publication_type.items():
                publication_type = publication_type.replace(src, target)
            row.append(publication_type)
            journal = entry.get("journal", "no journal")
            for src, target in replacements_journal.items():
                journal = journal.replace(src, target)
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
            file_name = entry.get("file", "no file")
            for src, target in replacements_filename1.items():
                file_name = file_name.replace(src, target)
            for src, target in replacements_filename2.items():
                file_name = file_name.replace(src, target)
            row.append(file_name)
            nr_cited_refs = entry.get(
                "number-of-cited-references", "no Number-of-Cited-References")
            row.append(nr_cited_refs)
            no_cited = entry.get("times-cited", "no Times-Cited")
            row.append(no_cited)
            doi = entry.get("doi", "no doi")
            row.append(doi)

            write_row(spreadsheet, row)

        bibtex_file.close()
    return



def gather(bibfilename, combined_bib_database):
    
    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        for entry in bib_database.entries:
            
            string_to_hash = ''
            if('author' in entry):
                string_to_hash += entry['author']
            if('title' in entry):
                string_to_hash += entry['title']
            if('year' in entry):
                string_to_hash += entry['year']
            if('journal' in entry):
                string_to_hash += entry['journal']
#            string_to_hash = string_to_hash.replace(' ','').lower()
            entry['GS_ID'] = hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
            print(entry['GS_ID'])
            
    if combined_bib_database is None:
        return bib_database

    # TODO: case if there are already entries in the combined_bib (need to compare/integrate)
    
    return bib_database


if __name__ == "__main__":
    
    target_file = 'data/processed/references.bib'
    

    if os.path.exists(os.path.join(os.getcwd(), target_file)):
        with open(target_file, 'r') as target_db:
            combined_bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(target_db, partial=True)
    else:
        print('No target database detected.')
        combined_bib_database = None

    writer = BibTexWriter()

    # TODO: this should become a for-loop
    #TODO: define preferences (start by processing e.g., WoS, then GS) or use heuristics to start with the highest quality (most complete) entries first.

    combined_bib_database = gather('data/raw/2018-12-01-GoogleScholar.bib', combined_bib_database)
#    combined_bib_database = gather('data/raw/2020-12-01-GoogleScholar.bib', combined_bib_database)

    writer.contents = ['comments', 'entries']
    writer.indent = '  '
    writer.order_entries_by = ('ID', 'author', 'year')
    bibtex_str = bibtexparser.dumps(combined_bib_database, writer)
    
    with open(target_file, 'w') as out:
        out.write(bibtex_str + '\n')