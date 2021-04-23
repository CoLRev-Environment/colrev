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
from fuzzywuzzy import fuzz

from string import ascii_lowercase

from crossref.restful import Works
from urllib.parse import quote_plus, urlencode

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)


def gather(bibfilename, combined_bib_database):
    
    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        for entry in bib_database.entries:
            print(entry['title'])
            
            string_to_hash = ''
            if('author' in entry):
                entry['author'] = entry['author'].replace('\n', ' ')
                # fix name format
                if (' and ' in entry['author'] and not ', ' in entry['author']) or (1 == len(entry['author'].split(' ')[0])):
                    names = entry['author'].split(' and ')
                    entry['author'] = ''
                    for name in names:
                        name_parts = name.split(' ')
                        print(' '.join(name_parts[1:]) + ', ' + name_parts[0])
                        name = ' '.join(name_parts[1:]) + ', ' + name_parts[0]
                        entry['author'] = entry['author'] + ' and ' + name
                    if entry['author'].startswith(' and '):
                        entry['author'] = entry['author'][5:]

                string_to_hash += entry['author']
            if('title' in entry):
                string_to_hash += entry['title']
                entry['title'] = entry['title'].replace('\n', ' ')
                words = entry['title'].split()
                if sum([word.isupper() for word in words])/len(words) > 0.8:
                    entry['title'] = entry['title'].capitalize()
            if('year' in entry):
                string_to_hash += entry['year']
            if('journal' in entry):
                string_to_hash += entry['journal']
            # string_to_hash = string_to_hash.replace(' ','').lower()
            if('booktitle' in entry):
                string_to_hash += entry['booktitle']
                words = entry['booktitle'].split()
                if sum([word.isupper() for word in words])/len(words) > 0.8:
                    entry['booktitle'] = ' '.join([word.capitalize() for word in words])
            if('abstract' in entry):
                entry['abstract'] = entry['abstract'].replace('\n', ' ')

            unwanted = ["note", "annote", "institution", "issn", "month", "researcherid-numbers", "unique-id", "orcid-numbers", "eissn", "type"]
            for val in unwanted:
                if(val in entry):
                    entry.pop(val)

            entry['hash_id'] = hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
            entry['ID'] = entry['author'].split(' ')[0] + (entry['year'] if 'year' in entry else '')
            entry['ID'] = re.sub("[^0-9a-zA-Z]+", "", entry['ID'])
            
            
            # TODO: quality-improvements (e.g., sentence case for titles, format author names, remove trailing dot...)
            # May even run a reference consolidation service?!?!
            # https://citationstyles.org/authors/#/titles-in-sentence-and-title-case
            
#            print(entry['title'])
            if "living spaces in digital nomads" in entry['title']:
                 
                api_url = "https://api.crossref.org/works?"
                params = {"rows": "5", "query.bibliographic": entry['title']}
                url = api_url + urlencode(params, quote_via=quote_plus)
                print(url)

                # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
                 
                 
                works = Works()
                print(entry['title'])
                #                print(entry['author'])
                w1 = works.query(container_title=entry['title'], author=entry['author'])
                for item in w1:
                    if fuzz.ratio(item['title'], entry['title']) > 60:
                        print(item['title'])
                        print('------------------')
                input('continue')


    for entry in bib_database.entries:
        
        if 0 == len(combined_bib_database.entries):
            combined_bib_database.entries.append(entry)
            continue
        
        if not entry['hash_id'] in [x['hash_id'] for x in combined_bib_database.entries]: 

            # Make sure the ID is unique (otherwise: append letters until this is the case)
            temp_id = entry['ID']
            letters = iter(ascii_lowercase)
            while temp_id in [x['ID'] for x in combined_bib_database.entries]:
                temp_id = entry['ID'] + next(letters)
            entry['ID'] = temp_id
            
            combined_bib_database.entries.append(entry)
    
    return combined_bib_database

if __name__ == "__main__":
    
    target_file = 'data/processed/references.bib'

    # fix formats
    # web of science exports field "Early Access Date" (spaces are a problem)
    print('TODO: replace Early Access Date in bibfile before loading!')

    if os.path.exists(os.path.join(os.getcwd(), target_file)):
        with open(target_file, 'r') as target_db:
            combined_bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True).parse_file(target_db, partial=True)
    else:
        print('No target database detected.')
        combined_bib_database = BibDatabase()

    writer = BibTexWriter()

    # TODO: this should become a for-loop

#    combined_bib_database = gather('data/raw/2018-12-01-GoogleScholar.bib', combined_bib_database)
#    combined_bib_database = gather('data/raw/2020-12-01-GoogleScholar.bib', combined_bib_database)
    combined_bib_database = gather('data/raw/2021-01-01-WebOfScience.bib', combined_bib_database)

    writer.contents = ['comments', 'entries']
    writer.indent = '    '
    writer.order_entries_by = ('ID', 'author', 'year')
    bibtex_str = bibtexparser.dumps(combined_bib_database, writer)
    
    with open(target_file, 'w') as out:
        out.write(bibtex_str + '\n')