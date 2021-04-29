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

from string import ascii_lowercase

#from crossref.restful import Works
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen, Request
import requests

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

EMPTY_RESULT = {
    "crossref_title": "",
    "similarity": 0,
    "doi": ""
}
MAX_RETRIES_ON_ERROR = 3

def crossref_query_title(title):
    api_url = "https://api.crossref.org/works?"
    params = {"rows": "5", "query.bibliographic": title}
    url = api_url + urlencode(params, quote_via=quote_plus)
#    print('Query Crossref API: ' + url)
    request = Request(url)
    request.add_header("User-Agent", "RecordCleanser (cleanse_records.py; mailto:gerit.wagner@hec.ca)")
    try:
        ret = urlopen(request)
        content = ret.read()
        data = json.loads(content)
        items = data["message"]["items"]
        most_similar = EMPTY_RESULT
        for item in items:
            if "title" not in item:
                continue
            title = item["title"].pop()
            result = {
                "crossref_title": title,
                "similarity": ratio(title.lower(), params["query.bibliographic"].lower()),
                "doi": item["DOI"]
            }
            if most_similar["similarity"] < result["similarity"]:
                most_similar = result
        return {"success": True, "result": most_similar}
    except HTTPError as httpe:
        return {"success": False, "result": EMPTY_RESULT, "exception": httpe}
    time.sleep(1)
    return

def doi2bib(doi):
  url = "http://dx.doi.org/" + doi

  headers = {"accept": "application/x-bibtex"}
  r = requests.get(url, headers = headers)

  return r.text

def quality_improvements(bibfilename):
    
    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        for entry in tqdm(bib_database.entries):

            # TODO: quality-improvements (e.g., sentence case for titles, format author names, remove trailing dot...)
            # May even run a reference consolidation service?!?!
            # https://citationstyles.org/authors/#/titles-in-sentence-and-title-case
            
            if('author' in entry):
                entry['author'] = entry['author'].rstrip().lstrip()
                # fix name format
                if (' and ' in entry['author'] and not ', ' in entry['author']) or (1 == len(entry['author'].split(' ')[0])):
                    names = entry['author'].split(' and ')
                    entry['author'] = ''
                    for name in names:
                        name_parts = name.split(' ')
                        name = ' '.join(name_parts[1:]) + ', ' + name_parts[0]
                        entry['author'] = entry['author'] + ' and ' + name
                    if entry['author'].startswith(' and '):
                        entry['author'] = entry['author'][5:]

            if('title' in entry):
                entry['title'] = entry['title']
                entry['title'] = re.sub('\s+',' ', entry['title'])
                words = entry['title'].split()
                if sum([word.isupper() for word in words])/len(words) > 0.8:
                    entry['title'] = entry['title'].capitalize()
#            if('year' in entry):
#                print('todo')
            if('journal' in entry):
                words = entry['journal'].split()
                if sum([word.isupper() for word in words])/len(words) > 0.8:
                    entry['journal'] = entry['journal'].capitalize()
            # string_to_hash = string_to_hash.replace(' ','').lower()
            if('booktitle' in entry):
                words = entry['booktitle'].split()
                if sum([word.isupper() for word in words])/len(words) > 0.8:
                    entry['booktitle'] = ' '.join([word.capitalize() for word in words])
            if('abstract' in entry):
                entry['abstract'] = entry['abstract'].replace('\n', ' ')
            
            # Check whether doi can be retrieved from CrossRef API based on meta-data
            # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
            if len(entry['title']) > 60 and 'doi' not in entry:
                try:
                    ret = crossref_query_title(entry['title'])
                    retries = 0
                    while not ret['success'] and retries < MAX_RETRIES_ON_ERROR:
                        retries += 1
                        msg = "Error while querying CrossRef API ({}), retrying ({})...".format(ret["exception"], retries)
    #                    print(msg)
                        ret = crossref_query_title(entry['title'])
                    if ret["result"]['similarity'] > 0.95:
                        entry['doi'] = ret["result"]['doi']
    #                    print('retrieved doi:' + entry['doi'])
                except:
                    pass
    
            # Retrieve metadata from DOI repository
            if 'doi' in entry:
                try:
                    full_data = doi2bib(entry['doi'])
                    database_records = bibtexparser.loads(full_data)
                    database_record = database_records.entries[0]
                    if 'title' in database_record: entry['title'] = database_record['title']
                    if 'author' in database_record: entry['author'] = database_record['author']
                    if 'journal' in database_record: entry['journal'] = database_record['journal']
                    if 'year' in database_record: entry['year'] = database_record['year']
                    if 'volume' in database_record: entry['volume'] = database_record['volume']
                    if 'number' in database_record: entry['number'] = database_record['number']
                    if 'pages' in database_record: entry['pages'] = database_record['pages']
                except:
                    pass


    writer = BibTexWriter()
    writer.contents = ['comments', 'entries']
    writer.indent = '    '
    writer.order_entries_by = ('ID', 'author', 'year')
    bibtex_str = bibtexparser.dumps(bib_database, writer)
    
    with open(bibfilename, 'w') as out:
        out.write(bibtex_str + '\n')
        
    return

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Cleanse records')
    
    bib_database = 'data/references.bib'
    assert os.path.exists(bib_database)

    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    quality_improvements(bib_database)
    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))

