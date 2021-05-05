#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import re
import os
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.customization import convert_to_unicode


def robust_append(string_to_hash, to_append):
    
    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub('\s+',' ', to_append)
    to_append = to_append.lower()
    
    string_to_hash = string_to_hash + to_append
    
    return string_to_hash

def create_hash(entry):
    string_to_hash = robust_append('', entry.get("author", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("author", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("title", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("journal", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("booktitle", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("year", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("volume", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("issue", ""))

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()


def save_bib_file(bib_database, target_file):
    
    for entry in bib_database.entries:
        if entry['ENTRYTYPE'] == 'article':
            entry['ENTRYTYPE'] = 'Article'
        if entry['ENTRYTYPE'] == 'book':
            entry['ENTRYTYPE'] = 'Book'
        if entry['ENTRYTYPE'] == 'inproceedings':
            entry['ENTRYTYPE'] = 'InProceedings'
    writer = BibTexWriter()
    if bib_database.comments == []:
        bib_database.comments = ['jabref-meta: databaseType:bibtex;']
    else:
        bib_database.comments.remove('% Encoding: UTF-8')
    writer.contents = ['entries', 'comments']
    writer.indent = '  '
    # The order should match JabRefs ordering of fields used when saving a file
    writer.display_order = ['author', 'booktitle', 'journal', 'title', 'year', 'editor', 'number', 'pages', 'series', 'volume', 'abstract', 'book-author', 'book-group-author', 'doi', 'hash_id']
    # to test this order, run merge_duplicates, add version in git, edit in JabRef and inspect differences
    # There seem to be dependencies in the save order (e.g., the pages are saved in a different position by JabRef if it is a book or an article)
    # the sort order seems to be a problem when @Books have both a title and a booktitle
    writer.order_entries_by = ('ID', 'author', 'year')
    writer.add_trailing_comma = True
    writer.align_values = True
    bibtex_str = bibtexparser.dumps(bib_database, writer)
    
    with open(target_file, 'w') as out:
        out.write(bibtex_str + '\n')


    # The following fixes the formatting to prevent JabRef from introducing format changes (there may be a more elegant way to achieve this)
    os.rename('data/references.bib', 'data/references_temp_2.bib')
    
    with open('data/references_temp_2.bib', 'r') as reader:
        lines = reader.readlines()
    
    with open('data/references.bib', 'w') as writer:
        writer.write('% Encoding: UTF-8\n\n')

        max_key_length = 0
        book = False
        saved_booktitle = ''
        saved_pages = ''
        for line in lines:
            
            # Note: padding depends on the longest field/key in each entry...
            if line[0] == '@':
                citation_key = line[line.find('{')+1:-2]
                # get longest key
                max_key_length = 0
                for entry in bib_database.entries:
                    if entry['ID'] == citation_key:
                        for key in entry.keys():
                            if 'ENTRYTYPE' == key: 
                                continue
                            if len(key) > max_key_length:
                                max_key_length = len(key)
                        break
                shorten = (18-max_key_length)*' ' + '='
                if line[0:6] == '@Book{':
                    book = True
                else:
                    book = False
                saved_booktitle = ''
                saved_pages = ''
            if max_key_length != 0:
                line = line.replace(shorten,' =')
            

            if book:
                if 'booktitle ' in line:
                    saved_booktitle = line
                    continue
                if 'pages ' in line:
                    saved_pages = line
                    continue

            writer.write(line)
            
            if book and 'year ' in line:
                writer.write (saved_booktitle)
            if book and 'hash_id ' in line:
                writer.write (saved_pages)

    # writer.write('@Comment{jabref-meta: databaseType:bibtex;}\n')

    os.remove('data/references_temp_2.bib')
    return