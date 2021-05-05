#! /usr/bin/env python
# -*- coding: utf-8 -*-

from bibtexparser.bibdatabase import BibDatabase

import os
import csv
from time import gmtime, strftime
from datetime import datetime
import re
import logging
from lxml import etree
import pandas as pd

import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

ns =    {'tei': '{http://www.tei-c.org/ns/1.0}',
         'w3' : '{http://www.w3.org/XML/1998/namespace}'}


def get_tei_files(directory):
    
    list_of_files = []
    for (dirpath, dirnames, filenames) in os.walk(directory):
        for filename in filenames:
            if filename.endswith('.tei.xml'): 
                list_of_files.append(os.sep.join([dirpath, filename]))
    return list_of_files

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
        author_string = ' and '.join(author_list)
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

def process_backward_search(tei):

    search_details = pd.read_csv('data/search/search_details.csv')
    
    if tei in search_details['source_url']:
        return

    with open(tei) as xml_file:
        root = etree.parse(xml_file).getroot()
    bibliography = extract_bibliography(root)
    db = BibDatabase()
    for index, row in bibliography.iterrows():
        entry = {}
        author_string = row['authors'].capitalize().replace(',', '').replace(' ', '')
        try:
            author_string = row['authors'].split(' ')[0].capitalize().replace(',', '')
        except:
            pass
        entry['ID'] = author_string + row['year']
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

    for entry in db.entries:
        empty_field_keys = [key for key in entry.keys() if entry[key] == '']
        for key in empty_field_keys:
            if entry[key] == '':
                del entry[key]

    bib_filename = tei.replace('.tei.xml', '') + 'bw_search.bib'
    utils.save_bib_file(db, bib_filename)

    if len(search_details.index) == 0:
        iteration_number = 1
    else:
        iteration_number = str(int(search_details['iteration'].max()))

    new_record = pd.DataFrame([['backward/' + bib_filename, len(db.entries), iteration_number, datetime.today().strftime('%Y-%m-%d'), datetime.today().strftime('%Y-%m-%d'), tei, '', 'automated_script', '']],
                                columns=['filename', 'number_records', 'iteration', 'date_start', 'date_completion', 'source_url', 'search_parameters', 'responsible', 'comment'])
    search_details = pd.concat([search_details, new_record])
    search_details.to_csv('data/search/search_details.csv', index=False, quoting=csv.QUOTE_ALL)

    return

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Backward search - Process')

    teis = get_tei_files('data/search/backward')

    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    for tei in teis:
        process_backward_search(tei)
    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    
    os.remove('data/search/backward_search_pdfs.csv')
    