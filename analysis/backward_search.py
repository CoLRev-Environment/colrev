#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode

import os
import json
import time
from time import gmtime, strftime
import re
import logging
from fuzzywuzzy import fuzz
from Levenshtein import ratio
from tqdm import tqdm

from lxml import etree

from string import ascii_lowercase

#from crossref.restful import Works
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen, Request
import requests
import pandas as pd

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

ns =    {'tei': '{http://www.tei-c.org/ns/1.0}',
         'w3' : '{http://www.w3.org/XML/1998/namespace}'}


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

def get_reference_title(reference):
    title_string = ''
    analytic_title_found = False
    if reference.find(ns['tei'] + 'analytic') is not None:
        if reference.find(ns['tei'] + 'analytic').find(ns['tei'] + 'title') is not None:
            if reference.find(ns['tei'] + 'analytic').find(ns['tei'] + 'title').text is not None:
                title_string = reference.find(ns['tei'] + 'analytic').find(ns['tei'] + 'title').text
                analytic_title_found = True
    if not analytic_title_found:
        if reference.find(ns['tei'] + 'monogr') is not None:
            if reference.find(ns['tei'] + 'monogr').find(ns['tei'] + 'title') is not None:
                if reference.find(ns['tei'] + 'monogr').find(ns['tei'] + 'title').text is not None:
                    title_string = reference.find(ns['tei'] + 'monogr').find(ns['tei'] + 'title').text
    try:
        words = title_string.split()
        if sum([word.isupper() for word in words])/len(words) > 0.8:
            words = [word.capitalize() for word in words]
            title_string = " ".join(words)
    except:
        pass
    return title_string

def get_reference_author(reference):
    author_list = []
    author_node = ''
    if reference.find(ns['tei'] + 'analytic') is not None:
        author_node = reference.find(ns['tei'] + 'analytic')
    elif reference.find(ns['tei'] + 'monogr') is not None:
        author_node = reference.find(ns['tei'] + 'monogr')
    
    if author_node == '':
        return ''
    
    for author in author_node.iterfind(ns['tei'] + 'author'):
        authorname = ''
        try:
            surname = author.find(ns['tei'] + 'persName').find(ns['tei'] + 'surname').text
        except:
            surname = ''
            pass
        try:
            forename = author.find(ns['tei'] + 'persName').find(ns['tei'] + 'forename').text
        except:
            forename = ''
            pass

        #check surname and prename len. and swap
        if(len(surname) < len(forename)):
            authorname = forename + ', ' + surname
        else:
            authorname = surname + ', ' + forename
        author_list.append(authorname)

    #fill author field with editor or organization if null
    if len(author_list) == 0:
        if reference.find(ns['tei'] + 'editor') is not None:
            author_list.append(reference.find(ns['tei'] + 'editor').text)
        elif reference.find(ns['tei'] + 'orgName') is not None:
            author_list.append(reference.find(ns['tei'] + 'orgName').text)

    author_string = ''
    for author in author_list:
        author_string = '; '.join(author_list)
    author_string = author_string.replace('\n', ' ').replace('\r', '')

    if author_string is None:
        author_string = ''

    return author_string

def get_reference_journal(reference):
    journal_title = ''
    if reference.find(ns['tei'] + 'monogr') is not None:
        journal_title = reference.find(ns['tei'] + 'monogr').find(ns['tei'] + 'title').text
    if journal_title is None:
        journal_title = ''
    return journal_title

def get_reference_journal_volume(reference):
    volume = ''
    try:
        if reference.find('.//' + ns['tei'] + 'monogr') is not None:
            journal_node = reference.find('.//' + ns['tei'] + 'monogr')
            imprint_node = journal_node.find('.//' + ns['tei'] + 'imprint')
            volume = imprint_node.find('.//' + ns['tei'] + "biblScope[@unit='volume']").text
    except:
        pass
    return volume

def get_reference_journal_issue(reference):
    issue = ''
    try:
        if reference.find('.//' + ns['tei'] + 'monogr') is not None:
            journal_node = reference.find('.//' + ns['tei'] + 'monogr')
            imprint_node = journal_node.find('.//' + ns['tei'] + 'imprint')
            issue = imprint_node.find('.//' + ns['tei'] + "biblScope[@unit='issue']").text
    except:
        pass
    return issue

def get_reference_year(reference):
    year_string = ''
    if reference.find(ns['tei'] + 'monogr') is not None:
        year = reference.find(ns['tei'] + 'monogr').find(ns['tei'] + 'imprint').find(ns['tei'] + 'date')
    elif reference.find(ns['tei'] + 'analytic') is not None:
        year = reference.find(ns['tei'] + 'analytic').find(ns['tei'] + 'imprint').find(ns['tei'] + 'date')

    if not year is None:
        for name, value in sorted(year.items()):
            if name == 'when':
                year_string = value
            else:
                year_string = 'NA'
    else:
        year_string = 'NA'
    year_string = re.sub(".*([1-2][0-9]{3}).*", "\\1", year_string)
    return year_string

def get_reference_pages(reference):
    pages = ''
    try:
        if reference.find('.//' + ns['tei'] + 'monogr') is not None:
            journal_node = reference.find('.//' + ns['tei'] + 'monogr')
            imprint_node = journal_node.find('.//' + ns['tei'] + 'imprint')
            page_node = imprint_node.find('.//' + ns['tei'] + "biblScope[@unit='page']")
            pages = page_node.get('from') + '--' + page_node.get('to')
    except:
        pass
    return pages

def get_reference_doi(reference):
    doi = ''
    try:
        if reference.find('.//' + ns['tei'] + 'idno') is not None:
            doi = reference.find('.//' + ns['tei'] + 'idno').text
    except:
        pass
    return doi

def extract_bibliography(root):
    BIBLIOGRAPHY = pd.DataFrame(columns = ['authors', 'title', 'year', 'journal', 'volume', 'issue', 'pages', 'doi'])

    for bibliography in root.iter(ns['tei'] + 'listBibl'):
        for reference in bibliography:
            ENTRY = pd.DataFrame.from_records([[get_reference_author(reference), 
                                                get_reference_title(reference), 
                                                get_reference_year(reference), 
                                                get_reference_journal(reference),
                                                get_reference_journal_volume(reference),
                                                get_reference_journal_issue(reference),
                                                get_reference_pages(reference),
                                                get_reference_doi(reference)]], 
                                              columns = ['authors',
                                                         'title', 
                                                         'year', 
                                                         'journal',
                                                         'volume',
                                                         'issue',
                                                         'pages',
                                                         'doi'])
            BIBLIOGRAPHY = BIBLIOGRAPHY.append(ENTRY)

    BIBLIOGRAPHY = BIBLIOGRAPHY.reset_index(drop=True)
    return BIBLIOGRAPHY

def backward_search(pdf):

    #TODO: possibly using docker-compose?    
#    if not tei_tools.start_grobid():
#        print('Cannot start Docker/Grobid')
#        return
#    
#    print('index file: ' + pdf)
#    root = tei_tools.get_tei_header(pdf)
#    if isinstance(root, str):
#        if root == 'NA':
#           print('Service not available')
#           return
#        else:
#            print('Service not available')
#
#        return
#    grobid with consolidation

    print('called')
    # replace the following with the get_tei(pdf, preprocess=False)    
    with open(pdf) as xml_file:
        root = etree.parse(xml_file).getroot()
#    print(root)
    bibliography = extract_bibliography(root)
#    print(bibliography)
    db = BibDatabase()
    for index, row in bibliography.iterrows():
#        print(row['authors'], row['title'], row['year'], row['journal'], row['volume'], row['issue'], row['pages'], row['doi'])
        entry = {}
        #.split()[0]
        entry['ID'] = row['authors'].capitalize() + row['year']
        entry["ENTRYTYPE"] = 'article'
        entry["author"] = row['authors']
        entry["journal"] = row['journal']
        entry["title"] = row['title']
        entry["year"] = row['year']
        entry["volume"] = row['volume']
        entry["issue"] = row['issue']
        entry["pages"] = row['pages']
        entry["doi"] = row['doi']
        if index == 0:
            db.entries = [entry]
        else:
            db.entries.append(entry)
    
    writer = BibTexWriter()
    writer.contents = ['comments', 'entries']
    writer.indent = '    '
    writer.order_entries_by = ('ID', 'author', 'year')
    bibtex_str = bibtexparser.dumps(db, writer)
    with open(pdf + 'bw_search.bib', 'w') as out:
        out.write(bibtex_str + '\n')

     
#    tei to bibtex
#    
#    save as YYYY-MM-DD-backward-search-CITATION_KEY.bib
    
    return

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Backward search')
    
    bibtex_file = 'data/references.bib'
    assert os.path.exists(bibtex_file)

    screen_file = 'data/screen.csv'
    assert os.path.exists(screen_file)

    pdfs = get_included_pdfs(screen_file, bibtex_file)
    
    pdfs = ['data/search/backward/test.tei.xml']

    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    for pdf in pdfs:
        backward_search(pdf)
    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
#
#    add YYYY-MM-DD-backward-search* to data/search/search_details.csv (and update search.py)