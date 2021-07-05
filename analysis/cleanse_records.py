#! /usr/bin/env python
import csv
import json
import logging
import os
import re
import sys
import time
from time import gmtime
from time import strftime
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen
from nameparser import HumanName

import bibtexparser
import git
import pandas as pd
import requests
import utils
from bibtexparser.bwriter import BibTexWriter
from Levenshtein import ratio
from tqdm import tqdm

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

EMPTY_RESULT = {
    'crossref_title': '',
    'similarity': 0,
    'doi': '',
}
MAX_RETRIES_ON_ERROR = 3


def crossref_query(entry):
    # https://github.com/CrossRef/rest-api-doc
    api_url = 'https://api.crossref.org/works?'
    params = {'rows': '5', 'query.bibliographic': entry['title']}
    url = api_url + urlencode(params, quote_via=quote_plus)
    request = Request(url)
    request.add_header(
        'User-Agent', 'RecordCleanser (mailto:gerit.wagner@hec.ca)',
    )
    try:
        ret = urlopen(request)
        content = ret.read()
        data = json.loads(content)
        items = data['message']['items']
        most_similar = EMPTY_RESULT
        for item in items:
            if 'title' not in item:
                continue
            
            # TODO: author
            try:
                title_similarity = ratio(
                        item['title'].pop().lower(),
                        entry['title'].lower(),
                    )
                # TODO: could also be a proceedings paper...
                container_similarity = ratio(
                        item['container-title'].pop().lower(),
                        entry['journal'].lower(),
                    )
                weights = [0.6, 0.4]
                similarities = [title_similarity,
                                    container_similarity]
            
                similarity = sum(similarities[g] * weights[g]
                                       for g in range(len(similarities)))
                
                result = {
                    'similarity': similarity,
                    'doi': item['DOI'],
                }
                if most_similar['similarity'] < result['similarity']:
                    most_similar = result
            except KeyError:
                pass
        return {'success': True, 'result': most_similar}
    except HTTPError as httpe:
        return {'success': False, 'result': EMPTY_RESULT, 'exception': httpe}
    time.sleep(1)
    return

def doi2json(doi):
    url = 'http://dx.doi.org/' + doi
    headers = {'accept': 'application/vnd.citationstyles.csl+json'}
    r = requests.get(url, headers=headers)
    return r.text


def cleanse(entry, bib_details):
    cleansed = True
    
    if 'author' in entry:
        entry['author'] = entry['author'].rstrip().lstrip()
        # fix name format
        if (1 == len(entry['author'].split(' ')[0])) or \
            (
                ', ' not in entry['author']
        ):
            names = entry['author'].split(' and ')
            entry['author'] = ''
            for name in names:
                # Note: https://github.com/derek73/python-nameparser
                # is very effective (maybe not perfect)
                parsed_name = HumanName(name)
                # TODO: if all capitalized:
                # https://nameparser.readthedocs.io/en/latest/usage.html#capitalization-support
                # name.capitalize(force=True)
                parsed_name.string_format = "{last} {suffix}, {first} ({nickname}) {middle}"
                entry['author'] = entry['author'] + ' and ' + str(parsed_name).replace(' , ', ', ')
            if entry['author'].startswith(' and '):
                entry['author'] = entry['author'][5:]

    if 'title' in entry:
        entry['title'] = re.sub(r'\s+', ' ', entry['title'])\
            .rstrip('.')
        entry['title'] = utils.title_if_mostly_upper_case(entry['title'])

    conf_strings = [
        'proceedings',
        'conference',
    ]
    # Consistency checks
    if 'journal' in entry:
        if any(
            conf_string in entry['journal'].lower()
            for conf_string in conf_strings
        ):
            print('WARNING: conference string in journal field: ',
                  entry['ID'],
                  entry['journal'])
            # entry['booktitle'] = entry['journal']
            # entry['ENTRYTYPE'] = 'inproceedings'
            # del entry['journal']
    if 'booktitle' in entry:
        if any(
            conf_string in entry['booktitle'].lower()
            for conf_string in conf_strings
        ):
            entry['ENTRYTYPE'] = 'inproceedings'

    # TODO: create a warning if any conference strings (ecis, icis, ..)
    # as stored in CONFERENCE_ABBREVIATIONS is in an article/book

    # Journal articles should not have booktitles/series set.
    if 'article' == entry['ENTRYTYPE']:
        if 'booktitle' in entry:
            if 'journal' not in entry:
                entry['journal'] = entry['booktitle']
                del entry['booktitle']
        if 'series' in entry:
            if 'journal' not in entry:
                entry['journal'] = entry['series']
                del entry['series']

    if 'book' == entry['ENTRYTYPE']:
        if 'series' in entry:
            if any(
                conf_string in entry['series'].lower()
                for conf_string in conf_strings
            ):
                conf_name = entry['series']
                del entry['series']
                entry['booktitle'] = conf_name
                entry['ENTRYTYPE'] = 'inproceedings'

    # Moved journal processing to combine_individual_search_results

    if 'booktitle' in entry:
        entry['booktitle'] = utils.title_if_mostly_upper_case(entry['booktitle'])

        # For ECIS/ICIS proceedings:
        entry['booktitle'] = \
            entry['booktitle'] \
            .replace(' Completed Research Papers', '')\
            .replace(' Completed Research', '')\
            .replace(' Research-in-Progress Papers', '')\
            .replace(' Research Papers', '')\
            .replace('- All Submissions', '')

        for i, row in CONFERENCE_ABBREVIATIONS.iterrows():
            stripped_booktitle = re.sub(
                r'\d{4}', '', entry['booktitle'])
            stripped_booktitle = re.sub(
                r'\d{1,2}th', '', stripped_booktitle)
            stripped_booktitle = re.sub(
                r'\d{1,2}nd', '', stripped_booktitle)
            stripped_booktitle = re.sub(
                r'\d{1,2}rd', '', stripped_booktitle)
            stripped_booktitle = re.sub(
                r'\d{1,2}st', '', stripped_booktitle)
            stripped_booktitle = re.sub(
                r'\([A-Z]{3,6}\)', '', stripped_booktitle)
            stripped_booktitle = stripped_booktitle\
                .replace('Proceedings of the', '')\
                .replace('Proceedings', '')\
                .rstrip()\
                .lstrip()

            if row['abbreviation'].lower() == \
                    stripped_booktitle.lower():
                entry['booktitle'] = row['conference']

    if 'article' == entry['ENTRYTYPE']:
        if 'journal' not in entry:
            if 'series' in entry:
                journal_string = entry['series']
                entry['journal'] = journal_string
                del entry['series']
    if 'abstract' in entry:
        entry['abstract'] = entry['abstract'].replace('\n', ' ')

    if 'pages' in entry:
        entry = utils.unify_pages_field(entry)

    # Check whether doi can be retrieved from CrossRef API
    # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
    if len(entry['title']) > 60 and 'doi' not in entry:
        try:
            ret = crossref_query(entry)
            retries = 0
            while not ret['success'] and \
                    retries < MAX_RETRIES_ON_ERROR:
                retries += 1
                ret = crossref_query(entry)
            if ret['result']['similarity'] > 0.95:
                entry['doi'] = ret['result']['doi']
        except KeyboardInterrupt:
            sys.exit()

    # Retrieve metadata from DOI repository
    if 'doi' in entry:
        try:
            full_data = doi2json(entry['doi'])
            retrieved_record = json.loads(full_data)
            # json_string = json.dumps(retrieved_record)
            # if 'crossmark' in json_string:
            #       print(retrieved_record)
            author_string = ''
            for author in retrieved_record.get('author', ''):
                if 'family' not in author:
                    continue
                if '' != author_string:
                    author_string = author_string + ' and '
                author_given = author.get('given', '')
                # Use local given name when no given name is provided by doi
                if '' == author_given:
                    local_author_string = [x for x in entry['author'].split(' and ') if author.get('family', '').lower() in x.lower()]
                    local_author = HumanName(local_author_string.pop())

                    author_string = author_string + \
                        author.get('family', '') + ', ' + \
                        local_author.first + ' ' + local_author.middle
                    # Note: the following should be used if there is an exception
                    # author_string = author_string + \
                    # author.get('family', '')
                else:
                    author_string = author_string + \
                        author.get('family', '') + ', ' + \
                        author.get('given', '')

            if not author_string == '':
                if utils.mostly_upper_case(author_string.replace(' and ', '').replace('Jr','')):

                    names = author_string.split(' and ')
                    entry['author'] = ''
                    for name in names:
                        # Note: https://github.com/derek73/python-nameparser
                        # is very effective (maybe not perfect)
                        parsed_name = HumanName(name)
                        parsed_name.capitalize(force=True)
                        parsed_name.string_format = "{last} {suffix}, {first} ({nickname}) {middle}"
                        entry['author'] = entry['author'] + ' and ' + str(parsed_name).replace(' , ', ', ')
                    if entry['author'].startswith(' and '):
                        entry['author'] = entry['author'][5:].rstrip().replace('  ', ' ')
                else:
                    entry['author'] = str(author_string).rstrip().replace('  ', ' ')
 
            retrieved_title = retrieved_record.get('title', '')
            if not retrieved_title == '':
                entry['title'] = \
                    str(re.sub(r'\s+', ' ', retrieved_title))\
                    .replace('\n', ' ')
            try:
                date_parts = \
                    retrieved_record['published-print']['date-parts']
                entry['year'] = str(date_parts[0][0])
            except KeyError:
                pass

            retrieved_pages = retrieved_record.get('page', '')
            if retrieved_pages != '':
                # DOI data often has only the first page.
                if not entry.get('pages', 'no_pages') in retrieved_pages \
                    and '-' in retrieved_pages:
                    entry['pages'] = utils.unify_pages_field(str(retrieved_pages))
            retrieved_volume = retrieved_record.get('volume', '')
            if not retrieved_volume == '':
                entry['volume'] = str(retrieved_volume)

            retrieved_issue = retrieved_record.get('issue', '')
            if not retrieved_issue == '':
                entry['number'] = str(retrieved_issue)
            retrieved_container_title = \
                str(retrieved_record.get('container-title', ''))
            if not retrieved_container_title == '':
                if 'series' in entry:
                    if entry['series'] != retrieved_container_title:

                        if 'journal' in retrieved_container_title:
                            entry['journal'] = \
                                retrieved_container_title
                        else:
                            entry['booktitle'] = \
                                retrieved_container_title

            if 'abstract' not in entry:
                retrieved_abstract = retrieved_record\
                    .get('abstract', '')
                if not retrieved_abstract == '':

                    retrieved_abstract = \
                        re.sub(
                            r'<\/?jats\:[^>]*>',
                            ' ',
                            retrieved_abstract,
                        )
                    retrieved_abstract = \
                        re.sub(r'\s+', ' ', retrieved_abstract)
                    entry['abstract'] = \
                        str(retrieved_abstract).replace('\n', '')\
                        .lstrip().rstrip()
        except IndexError:
            print('Index error (authors?) for ' + entry['ID'])
            cleansed = False
            pass
        except json.decoder.JSONDecodeError:
            print('Doi retrieval error: ' + entry['ID'])
            cleansed = False
            pass
        except TypeError:
            print('Type error: ' + entry['ID'])
            cleansed = False
            pass

    if cleansed:

        # Recreate citation_keys
        # (mainly if it differs, i.e., if there are changes in authors/years)
        try:
            entry['ID'] = utils.generate_citation_key(entry, bib_database)
        except utils.CitationKeyPropagationError:
            print('WARNING: cleansing entry with propagated citation_key:',
                  entry['ID'])
            pass
    
        # Note: as soon as a single hash_id
        # (in an entry containing multiple hash_ids) has been cleansed,
        # all other hash_ids are considered as cleansed
        # (since the have been merged with/reviewed a cleansed record)
        if 'hash_id' in entry:
            for individual_hash_id in entry['hash_id'].split(','):
                new_record = pd.DataFrame(
                    [[individual_hash_id, 'yes']], columns=[
                        'hash_id', 'cleansed',
                    ],
                )
                bib_details = pd.concat([bib_details, new_record])

    return entry, cleansed, bib_details

def entry_cleansed(entry, bib_details):
    # If there is no entry in the bib_details, it needs to be cleansed.
    entry_is_cleansed = False
    # This means all entries without a hash_id are cleansed
    if 'hash_id' in entry:
        for individual_hash_id in entry['hash_id'].split(','):
            if 0 < len(
                bib_details[
                    bib_details['hash_id'] == individual_hash_id
                ],
            ):
                entry_is_cleansed = True
    return entry_is_cleansed

def quality_improvements(bib_database):

    bib_details_path = 'data/search/bib_details.csv'
    if os.path.exists(bib_details_path):
        bib_details = pd.read_csv(bib_details_path)
    else:
        bib_details = pd.DataFrame(columns=['hash_id', 'cleansed'])

    # If a more detailed (step-wise) cleansing process is needed,
    # the bib_details would need more field (cleansing_1, cleansing_2, ...)

#    skipped_all = False

    for entry in tqdm(bib_database.entries):
        
#        if not 'Doolin' in entry['ID']:
#            continue
#        if 'Piel2017' == entry['ID']:
#            skipped_all = True
#        if not skipped_all:
#            continue

        if entry_cleansed(entry, bib_details):
            continue

        entry, cleansed, bib_details = cleanse(entry, bib_details)

        if not cleansed:
            continue

        utils.save_bib_file(bib_database, 'data/references.bib')

        bib_details.sort_values(by=['hash_id'], inplace=True)
        bib_details.to_csv(
            bib_details_path, index=False,
            quoting=csv.QUOTE_ALL,
        )

    return bib_database


if __name__ == '__main__':
    
    # To test:
    # bibtex_str = "@article{...\n ...}"
    # bib_database = bibtexparser.loads(bibtex_str)
    # entry = bib_database.entries[0]

    print('')
    print('')

    print('Cleanse records')

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    r = git.Repo('data')

    if r.is_dirty():
        print('Commit files before cleansing.')
        sys.exit()

    # idea: include all submodules (starting with crowd_resource_*) by default
    # (automatically?) set up a corresponding submodule if necessary (discover_resources())
    JOURNAL_ABBREVIATIONS = pd.read_csv('data/crowd_resource_information_systems/lexicon/journals/JOURNAL_ABBREVIATIONS.csv')
    JOURNAL_VARIATIONS = pd.read_csv('data/crowd_resource_information_systems/lexicon/journals/JOURNAL_VARIATIONS.csv')
    CONFERENCE_ABBREVIATIONS = \
        pd.read_csv('data/crowd_resource_information_systems/lexicon/journals/CONFERENCE_ABBREVIATIONS.csv')

    print(strftime('%Y-%m-%d %H:%M:%S', gmtime()))
    bib_database = quality_improvements(bib_database)
    print(strftime('%Y-%m-%d %H:%M:%S', gmtime()))

    r.index.add(['references.bib'])
    # Note: we may want to remove this at some point.
    r.index.add(['search/bib_details.csv'])

    r.index.commit(
        'Cleanse references.bib',
        author=git.Actor('script:cleanse_records.py', ''),
    )

    print('Created commit: Cleanse references.bib')
