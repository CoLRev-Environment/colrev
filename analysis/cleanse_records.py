#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode

import os
import csv
import json
import time
from time import gmtime, strftime
import re
import logging
from Levenshtein import ratio
from tqdm import tqdm

#from crossref.restful import Works
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen, Request
import requests
import pandas as pd
import sys

import shutil

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

def doi2json(doi):
    url = "http://dx.doi.org/" + doi
    headers = {"accept": "application/vnd.citationstyles.csl+json"}
    r = requests.get(url, headers = headers)
    return r.text

def quality_improvements(bibfilename):
    
    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
                
        bib_details_path = 'data/search/bib_details.csv'
        if os.path.exists(bib_details_path):
            bib_details = pd.read_csv(bib_details_path)
        else:
            bib_details = pd.DataFrame(columns=['hash_id', 'cleansed'])

        for entry in tqdm(bib_database.entries):
    
            # TODO: reconsider the logic considering iterations
            # Note: the case cleansed==no should not occur... if there is no entry in the bib_details, it needs to be cleansed.
            if  0 == len(bib_details[bib_details['hash_id'] == entry['hash_id']]):
                new_record = pd.DataFrame([[entry['hash_id'],'yes']], columns=['hash_id','cleansed'])
                bib_details = pd.concat([bib_details, new_record])

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
                        
                # Consistency checks
                if 'journal' in entry:
                    if any(conf_string in entry['journal'].lower() for conf_string in ['proceedings', 'conference', 'ECIS', 'AMICS', 'ICIS', 'PACIS', 'HICSS']):
                        conf_name = entry['journal']
                        del entry['journal']
                        entry['booktitle'] = conf_name
                        entry['ENTRYTYPE'] = 'inproceedings'
    
                if 'book' == entry['ENTRYTYPE']:
                    if 'series' in entry:
                        if any(conf_string in entry['series'].lower() for conf_string in ['proceedings', 'conference', 'ECIS', 'AMICS', 'ICIS', 'PACIS', 'HICSS']):                        
                            conf_name = entry['series']
                            del entry['series']
                            entry['booktitle'] = conf_name
                            entry['ENTRYTYPE'] = 'inproceedings'
                            
                if('journal' in entry):
                    words = entry['journal'].split()
                    if sum([word.isupper() for word in words])/len(words) > 0.8:
                        entry['journal'] = entry['journal'].capitalize()
                        
                        for i, row in JOURNAL_VARIATIONS.iterrows():
                             if entry['journal'].lower() == row['variation'].lower():
                                 entry['journal'] = row['journal']
                        for i, row in JOURNAL_ABBREVIATIONS.iterrows():
                             if entry['journal'].lower() == row['abbreviation'].lower():
                                 entry['journal'] = row['journal']

                if('booktitle' in entry):
                    words = entry['booktitle'].split()
                    if sum([word.isupper() for word in words])/len(words) > 0.8:
                        entry['booktitle'] = ' '.join([word.capitalize() for word in words])
                        # For ECIS/ICIS proceedings:
                        entry['booktitle'] = entry['booktitle'].replace(' Completed Research Papers','').replace(' Completed Research','').replace(' Research-in-Progress Papers','').replace(' Research Papers','')
                        
                        for i, row in CONFERENCE_ABBREVIATIONS.iterrows():
                             if row['abbreviation'].lower() in entry['booktitle'].lower():
                                 entry['booktitle'] = row['conference']
                        
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
                            # msg = "Error while querying CrossRef API ({}), retrying ({})...".format(ret["exception"], retries)
                            # print(msg)
                            ret = crossref_query_title(entry['title'])
                        if ret["result"]['similarity'] > 0.95:
                            entry['doi'] = ret["result"]['doi']
                            # print('retrieved doi:' + entry['doi'])
                    except KeyboardInterrupt:
                        sys.exit()
        
                # Retrieve metadata from DOI repository
                if 'doi' in entry:
                    try:
                        full_data = doi2json(entry['doi'])
                        retrieved_record = json.loads(full_data)
                        author_string = ''
                        for author in retrieved_record.get('author', ''):
                            if not 'family' in author:
                                continue
                            if '' != author_string: author_string = author_string + ' and '
                            author_string = author_string + author.get('family', '') + ', ' + author.get('given', '')
                        if not author_string == '':
                            entry['author'] = str(author_string)
                        
                        retrieved_title = retrieved_record.get('title', '')
                        if not retrieved_title == '':
                            entry['title'] = str(retrieved_title).replace('\n','')
                        try:
                            entry['year'] = str(retrieved_record['published-print']['date-parts'][0][0])
                        except:
                            pass
    
                        retrieved_pages = retrieved_record.get('page', '')
                        if retrieved_pages != '':
                            if 1 == retrieved_pages.count('-'):
                                retrieved_pages = str(retrieved_pages).replace('-', '--')
                            entry['pages'] = str(retrieved_pages)
                        retrieved_volume = retrieved_record.get('volume', '')
                        if not retrieved_volume == '':
                            entry['volume'] = str(retrieved_volume)
                        
                        retrieved_issue = retrieved_record.get('issue', '')
                        if not retrieved_issue == '':
                            entry['number'] =  str(retrieved_issue)
                        retrieved_container_title = str(retrieved_record.get('container-title', ''))
                        if not retrieved_container_title == '':
                            if 'series' in entry:
                                if not entry['series'] == retrieved_container_title:
                                    
                                    if 'journal' in retrieved_container_title:
                                        entry['journal'] = retrieved_container_title
                                    else:
                                        entry['booktitle'] =  retrieved_container_title
    
                    except:
                        pass

            
            writer = BibTexWriter()
            writer.contents = ['comments', 'entries']
            writer.indent = '  '
            writer.display_order = ['author', 'booktitle', 'journal', 'title', 'year', 'number', 'pages', 'volume', 'doi', 'hash_id']
            writer.order_entries_by = ('ID', 'author', 'year')
            bibtex_str = bibtexparser.dumps(bib_database, writer)
            
            with open(bibfilename, 'w') as out:
                out.write(bibtex_str + '\n')

            bib_details.to_csv(bib_details_path, index=False, quoting=csv.QUOTE_ALL)
    return

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Cleanse records')
    
    bib_database = 'data/references.bib'
    assert os.path.exists(bib_database)

    JOURNAL_ABBREVIATIONS = pd.read_csv('analysis/JOURNAL_ABBREVIATIONS.csv')
    JOURNAL_VARIATIONS = pd.read_csv('analysis/JOURNAL_VARIATIONS.csv')
    CONFERENCE_ABBREVIATIONS = pd.read_csv('analysis/CONFERENCE_ABBREVIATIONS.csv')

    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    quality_improvements(bib_database)
    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    
#   shutil.copyfile(bib_database, 'data/references_last_automated.bib')
