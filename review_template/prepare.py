#! /usr/bin/env python
import collections
import json
import logging
import multiprocessing as mp
import os
import pprint
import re
import sys
import urllib

import bibtexparser
import click
import dictdiffer
import git
import pandas as pd
import requests
from fuzzywuzzy import fuzz
from nameparser import HumanName

from review_template import dedupe
from review_template import process
from review_template import repo_setup
from review_template import utils

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
BATCH_SIZE = repo_setup.config['BATCH_SIZE']
EMAIL = repo_setup.config['EMAIL']
pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)
PAD = 0

prepared, need_manual_prep = 0, 0

current_batch_counter = mp.Value('i', 0)


def retrieve_local_resources():

    if os.path.exists('lexicon/JOURNAL_ABBREVIATIONS.csv'):
        JOURNAL_ABBREVIATIONS = pd.read_csv(
            'lexicon/JOURNAL_ABBREVIATIONS.csv')
    else:
        JOURNAL_ABBREVIATIONS = pd.DataFrame(
            [], columns=['journal', 'abbreviation'])

    if os.path.exists('lexicon/JOURNAL_VARIATIONS.csv'):
        JOURNAL_VARIATIONS = pd.read_csv('lexicon/JOURNAL_VARIATIONS.csv')
    else:
        JOURNAL_VARIATIONS = pd.DataFrame([], columns=['journal', 'variation'])

    if os.path.exists('lexicon/CONFERENCE_ABBREVIATIONS.csv'):
        CONFERENCE_ABBREVIATIONS = \
            pd.read_csv('lexicon/CONFERENCE_ABBREVIATIONS.csv')
    else:
        CONFERENCE_ABBREVIATIONS = pd.DataFrame(
            [], columns=['conference', 'abbreviation'])

    return JOURNAL_ABBREVIATIONS, JOURNAL_VARIATIONS, CONFERENCE_ABBREVIATIONS


def retrieve_crowd_resources():

    JOURNAL_ABBREVIATIONS = pd.DataFrame(
        [], columns=['journal', 'abbreviation'])
    JOURNAL_VARIATIONS = pd.DataFrame([], columns=['journal', 'variation'])
    CONFERENCE_ABBREVIATIONS = pd.DataFrame(
        [], columns=['conference', 'abbreviation'])

    for resource in [x for x in os.listdir() if 'crowd_resource_' == x[:15]]:

        JOURNAL_ABBREVIATIONS_ADD = pd.read_csv(
            resource + '/lexicon/JOURNAL_ABBREVIATIONS.csv')
        JOURNAL_ABBREVIATIONS = pd.concat([JOURNAL_ABBREVIATIONS,
                                           JOURNAL_ABBREVIATIONS_ADD])

        JOURNAL_VARIATIONS_ADD = pd.read_csv(
            resource + '/lexicon/JOURNAL_VARIATIONS.csv')
        JOURNAL_VARIATIONS = pd.concat([JOURNAL_VARIATIONS,
                                        JOURNAL_VARIATIONS_ADD])

        CONFERENCE_ABBREVIATIONS_ADD = pd.read_csv(
            resource + '/lexicon/CONFERENCE_ABBREVIATIONS.csv')
        CONFERENCE_ABBREVIATIONS = pd.concat([CONFERENCE_ABBREVIATIONS,
                                              CONFERENCE_ABBREVIATIONS_ADD])

    return JOURNAL_ABBREVIATIONS, JOURNAL_VARIATIONS, CONFERENCE_ABBREVIATIONS


def correct_recordtype(record):

    conf_strings = [
        'proceedings',
        'conference',
    ]

    for i, row in LOCAL_CONFERENCE_ABBREVIATIONS.iterrows():
        conf_strings.append(row['abbreviation'].lower())
        conf_strings.append(row['conference'].lower())

    # Consistency checks
    if 'journal' in record:
        if any(x in record['journal'].lower() for x in conf_strings):
            record.update(booktitle=record['journal'])
            record.update(ENTRYTYPE='inproceedings')
            del record['journal']
    if 'booktitle' in record:
        if any(x in record['booktitle'].lower() for x in conf_strings):
            record.update(ENTRYTYPE='inproceedings')

    if 'dissertation' in record.get('fulltext', 'NA').lower() and \
            record['ENTRYTYPE'] != 'phdthesis':
        prior_e_type = record['ENTRYTYPE']
        record.update(ENTRYTYPE='phdthesis')
        logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                     f'Set from {prior_e_type} to phdthesis '
                     '("dissertation" in fulltext link)')
        # TODO: if school is not set: using named entity recognition or
        # following links: detect the school and set the field

    if 'thesis' in record.get('fulltext', 'NA').lower() and \
            record['ENTRYTYPE'] != 'phdthesis':
        prior_e_type = record['ENTRYTYPE']
        record.update(ENTRYTYPE='phdthesis')
        logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                     f'Set from {prior_e_type} to phdthesis '
                     '("thesis" in fulltext link)')
        # TODO: if school is not set: using named entity recognition or
        # following links: detect the school and set the field

    # TODO: create a warning if any conference strings (ecis, icis, ..)
    # as stored in CONFERENCE_ABBREVIATIONS is in an article/book

    # Journal articles should not have booktitles/series set.
    if 'article' == record['ENTRYTYPE']:
        if 'booktitle' in record:
            if 'journal' not in record:
                record.update(journal=record['booktitle'])
                del record['booktitle']
        if 'series' in record:
            if 'journal' not in record:
                record.update(journal=record['series'])
                del record['series']

    if 'book' == record['ENTRYTYPE']:
        if 'series' in record:
            if any(x in record['series'].lower() for x in conf_strings):
                conf_name = record['series']
                del record['series']
                record.update(booktitle=conf_name)
                record.update(ENTRYTYPE='inproceedings')

    if 'article' == record['ENTRYTYPE']:
        if 'journal' not in record:
            if 'series' in record:
                journal_string = record['series']
                record.update(journal=journal_string)
                del record['series']

    return record


def homogenize_record(record):

    fields_to_process = [
        'author', 'year', 'title',
        'journal', 'booktitle', 'series',
        'volume', 'number', 'pages', 'doi',
        'abstract'
    ]
    for field in fields_to_process:
        if field in record:
            record[field] = record[field].replace('\n', ' ')\
                .rstrip().lstrip()\
                .replace('{', '').replace('}', '')

    if 'author' in record:
        # DBLP appends identifiers to non-unique authors
        record.update(author=str(re.sub(r'[0-9]{4}', '', record['author'])))

        # fix name format
        if (1 == len(record['author'].split(' ')[0])) or \
                (', ' not in record['author']):
            record.update(author=format_author_field(record['author']))

    if 'title' in record:
        record.update(title=re.sub(r'\s+', ' ', record['title']).rstrip('.'))
        record.update(title=title_if_mostly_upper_case(record['title']))

    if 'booktitle' in record:
        record.update(booktitle=title_if_mostly_upper_case(
            record['booktitle']))

        stripped_btitle = re.sub(r'\d{4}', '', record['booktitle'])
        stripped_btitle = re.sub(r'\d{1,2}th', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}nd', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}rd', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}st', '', stripped_btitle)
        stripped_btitle = re.sub(r'\([A-Z]{3,6}\)', '', stripped_btitle)
        stripped_btitle = stripped_btitle.replace('Proceedings of the', '')\
            .replace('Proceedings', '')
        record.update(booktitle=stripped_btitle)

    if 'journal' in record:
        if len(record['journal']) > 10:
            record.update(
                journal=title_if_mostly_upper_case(record['journal']))

    if 'pages' in record:
        record.update(pages=unify_pages_field(record['pages']))
        if not re.match(r'^\d*$', record['pages']) and \
                not re.match(r'^\d*--\d*$', record['pages']) and\
                not re.match(r'^[xivXIV]*--[xivXIV]*$', record['pages']):
            logging.info(f' {record["ID"]}:'.ljust(PAD, ' ') +
                         f'Unusual pages: {record["pages"]}')

    if 'doi' in record:
        record.update(doi=record['doi'].replace('http://dx.doi.org/', ''))

    if 'number' not in record and 'issue' in record:
        record.update(number=record['issue'])
        del record['issue']

    return record


LOCAL_JOURNAL_ABBREVIATIONS, \
    LOCAL_JOURNAL_VARIATIONS, \
    LOCAL_CONFERENCE_ABBREVIATIONS = \
    retrieve_local_resources()


def apply_local_rules(record):

    if 'journal' in record:
        for i, row in LOCAL_JOURNAL_ABBREVIATIONS.iterrows():
            if row['abbreviation'].lower() == record['journal'].lower():
                record.update(journal=row['journal'])

        for i, row in LOCAL_JOURNAL_VARIATIONS.iterrows():
            if row['variation'].lower() == record['journal'].lower():
                record.update(journal=row['journal'])

    if 'booktitle' in record:
        for i, row in LOCAL_CONFERENCE_ABBREVIATIONS.iterrows():
            if row['abbreviation'].lower() == record['booktitle'].lower():
                record.update(booktitle=row['conference'])

    return record


CR_JOURNAL_ABBREVIATIONS, \
    CR_JOURNAL_VARIATIONS, \
    CR_CONFERENCE_ABBREVIATIONS = \
    retrieve_crowd_resources()


def apply_crowd_rules(record):

    if 'journal' in record:
        for i, row in CR_JOURNAL_ABBREVIATIONS.iterrows():
            if row['abbreviation'].lower() == record['journal'].lower():
                record.update(journal=row['journal'])

        for i, row in CR_JOURNAL_VARIATIONS.iterrows():
            if row['variation'].lower() == record['journal'].lower():
                record.update(journal=row['journal'])

    if 'booktitle' in record:
        for i, row in CR_CONFERENCE_ABBREVIATIONS.iterrows():
            if row['abbreviation'].lower() == record['booktitle'].lower():
                record.update(booktitle=row['conference'])

    return record


def mostly_upper_case(input_string):
    # also in repo_setup.py - consider updating it separately
    if not re.match(r'[a-zA-Z]+', input_string):
        return input_string
    input_string = input_string.replace('.', '').replace(',', '')
    words = input_string.split()
    return sum(word.isupper() for word in words)/len(words) > 0.8


def title_if_mostly_upper_case(input_string):
    if not re.match(r'[a-zA-Z]+', input_string):
        return input_string
    words = input_string.split()
    if sum(word.isupper() for word in words)/len(words) > 0.8:
        return input_string.capitalize()
    else:
        return input_string


def format_author_field(input_string):

    input_string = input_string.replace('\n', ' ')
    # DBLP appends identifiers to non-unique authors
    input_string = str(re.sub(r'[0-9]{4}', '', input_string))

    names = input_string.split(' and ')
    author_string = ''
    for name in names:
        # Note: https://github.com/derek73/python-nameparser
        # is very effective (maybe not perfect)

        parsed_name = HumanName(name)
        if mostly_upper_case(input_string
                             .replace(' and ', '')
                             .replace('Jr', '')):
            parsed_name.capitalize(force=True)

        parsed_name.string_format = \
            '{last} {suffix}, {first} {middle}'
        # '{last} {suffix}, {first} ({nickname}) {middle}'
        author_name_string = str(parsed_name).replace(' , ', ', ')
        # Note: there are errors for the following author:
        # JR Cromwell and HK Gardner
        # The JR is probably recognized as Junior.
        # Check whether this is fixed in the Grobid name parser

        if author_string == '':
            author_string = author_name_string
        else:
            author_string = author_string + ' and ' + author_name_string

    return author_string


def get_container_title(record):
    container_title = 'NA'
    if 'ENTRYTYPE' not in record:
        container_title = record.get('journal', record.get('booktitle', 'NA'))
    else:
        if 'article' == record['ENTRYTYPE']:
            container_title = record.get('journal', 'NA')
        if 'inproceedings' == record['ENTRYTYPE']:
            container_title = record.get('booktitle', 'NA')
        if 'book' == record['ENTRYTYPE']:
            container_title = record.get('title', 'NA')
        if 'inbook' == record['ENTRYTYPE']:
            container_title = record.get('booktitle', 'NA')
    return container_title


def unify_pages_field(input_string):
    # also in repo_setup.py - consider updating it separately
    if not isinstance(input_string, str):
        return input_string
    if not re.match(r'^\d*--\d*$', input_string) and '--' not in input_string:
        input_string = input_string.replace('-', '--')\
            .replace('–', '--')\
            .replace('----', '--')\
            .replace(' -- ', '--')\
            .rstrip('.')
    return input_string


def get_md_from_doi(record):
    if 'doi' not in record:
        return record

    record = retrieve_doi_metadata(record)
    record.update(metadata_source='DOI.ORG')

    return record


def json_to_record(item):
    # Note: the format differst between crossref and doi.org

    record = {}

    if 'title' in item:
        retrieved_title = item['title']
        if isinstance(retrieved_title, list):
            retrieved_title = retrieved_title[0]
        retrieved_title = \
            re.sub(r'\s+', ' ', str(retrieved_title)).replace('\n', ' ')
        record.update(title=retrieved_title)

    container_title = None
    if 'container-title' in item:
        container_title = item['container-title']
        if isinstance(container_title, list):
            container_title = container_title[0]

    if 'type' in item:
        if 'journal-article' == item.get('type', 'NA'):
            record.update(ENTRYTYPE='article')
            if container_title is not None:
                record.update(journal=container_title)
        if 'proceedings-article' == item.get('type', 'NA'):
            record.update(ENTRYTYPE='inproceedings')
            if container_title is not None:
                record.update(booktitle=container_title)
        if 'book' == item.get('type', 'NA'):
            record.update(ENTRYTYPE='book')
            if container_title is not None:
                record.update(series=container_title)

    if 'DOI' in item:
        record.update(doi=item['DOI'])

    authors = [f'{author["family"]}, {author.get("given", "")}'
               for author in item['author']
               if 'family' in author]
    authors_string = ' and '.join(authors)
    # authors_string = format_author_field(authors_string)
    record.update(author=authors_string)

    try:
        if 'published-print' in item:
            date_parts = item['published-print']['date-parts']
            record.update(year=str(date_parts[0][0]))
        elif 'published-online' in item:
            date_parts = item['published-online']['date-parts']
            record.update(year=str(date_parts[0][0]))
    except KeyError:
        pass

    retrieved_pages = item.get('page', '')
    if retrieved_pages != '':
        # DOI data often has only the first page.
        if not record.get('pages', 'no_pages') in retrieved_pages \
                and '-' in retrieved_pages:
            record.update(pages=unify_pages_field(str(retrieved_pages)))
    retrieved_volume = item.get('volume', '')
    if not retrieved_volume == '':
        record.update(volume=str(retrieved_volume))

    retrieved_number = item.get('issue', '')
    if 'journal-issue' in item:
        if 'issue' in item['journal-issue']:
            retrieved_number = item['journal-issue']['issue']
    if not retrieved_number == '':
        record.update(number=str(retrieved_number))

    if 'abstract' in item:
        retrieved_abstract = item['abstract']
        if not retrieved_abstract == '':
            retrieved_abstract = \
                re.sub(r'<\/?jats\:[^>]*>', ' ', retrieved_abstract)
            retrieved_abstract = re.sub(r'\s+', ' ', retrieved_abstract)
            retrieved_abstract = str(retrieved_abstract).replace('\n', '')\
                .lstrip().rstrip()
            record.update(abstract=retrieved_abstract)
    return record


def crossref_query(record):
    # https://github.com/CrossRef/rest-api-doc
    api_url = 'https://api.crossref.org/works?'
    bibliographic = record['title'] + ' ' + record.get('year', '')
    bibliographic = bibliographic.replace('...', '').replace('…', '')
    container_title = get_container_title(record)
    container_title = container_title.replace('...', '').replace('…', '')
    author_string = record['author'].replace('...', '').replace('…', '')
    params = {'rows': '5',
              'query.bibliographic': bibliographic,
              'query.author': author_string,
              'query.container-title': container_title}
    url = api_url + urllib.parse.urlencode(params)
    headers = {'user-agent': f'{__name__} (mailto:{EMAIL})'}
    try:
        ret = requests.get(url, headers=headers)
        if ret.status_code != 200:
            logging.debug(
                f'crossref_query failed with status {ret.status_code}')
            return None

        data = json.loads(ret.text)
        items = data['message']['items']
        most_similar = 0
        most_similar_record = None
        for item in items:
            if 'title' not in item:
                continue

            retrieved_record = json_to_record(item)

            title_similarity = fuzz.partial_ratio(
                retrieved_record['title'].lower(),
                record['title'].lower(),
            )
            container_similarity = fuzz.partial_ratio(
                get_container_title(retrieved_record).lower(),
                get_container_title(record).lower(),
            )
            weights = [0.6, 0.4]
            similarities = [title_similarity, container_similarity]

            similarity = sum(similarities[g] * weights[g]
                             for g in range(len(similarities)))
            # logging.debug(f'record: {pp.pformat(record)}')
            # logging.debug(f'similarities: {similarities}')
            # logging.debug(f'similarity: {similarity}')

            if most_similar < similarity:
                most_similar = similarity
                most_similar_record = retrieved_record
    except requests.exceptions.ConnectionError:
        logging.error('requests.exceptions.ConnectionError in crossref_query')
        return None

    return most_similar_record


def get_md_from_crossref(record):
    if ('title' not in record) or ('doi' in record) or \
            is_complete_metadata_source(record):
        return record
    # To test the metadata provided for a particular DOI use:
    # https://api.crossref.org/works/DOI

    logging.debug(f'get_md_from_crossref({record["ID"]})')
    MAX_RETRIES_ON_ERROR = 3
    # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
    if len(record['title']) > 35:
        try:

            retrieved_record = crossref_query(record)
            retries = 0
            while not retrieved_record and retries < MAX_RETRIES_ON_ERROR:
                retries += 1
                retrieved_record = crossref_query(record)

            if retrieved_record is None:
                return record

            similarity = dedupe.get_record_similarity(record.copy(),
                                                      retrieved_record.copy())
            logging.debug(f'crossref similarity: {similarity}')
            if similarity > 0.80:
                for key, val in retrieved_record.items():
                    record[key] = val
                record.update(metadata_source='CROSSREF')

        except KeyboardInterrupt:
            sys.exit()
    return record


def sem_scholar_json_to_record(item, record):
    retrieved_record = {}
    if 'authors' in item:
        authors_string = ' and '.join([author['name']
                                       for author in item['authors']
                                       if 'name' in author])
        authors_string = format_author_field(authors_string)
        retrieved_record.update(author=authors_string)
    if 'abstract' in item:
        retrieved_record.update(abstract=item['abstract'])
    if 'doi' in item:
        retrieved_record.update(doi=item['doi'])
    if 'title' in item:
        retrieved_record.update(title=item['title'])
    if 'year' in item:
        retrieved_record.update(year=item['year'])
    # Note: semantic scholar does not provide data on the type of venue.
    # we therefore use the original ENTRYTYPE
    if 'venue' in item:
        if 'journal' in record:
            retrieved_record.update(journal=item['venue'])
        if 'booktitle' in record:
            retrieved_record.update(booktitle=item['venue'])
    if 'url' in item:
        retrieved_record.update(sem_scholar_id=item['url'])

    keys_to_drop = []
    for key, value in retrieved_record.items():
        retrieved_record[key] =  \
            str(value).replace('\n', ' ').lstrip().rstrip()
        if value in ['', 'None'] or value is None:
            keys_to_drop.append(key)
    for key in keys_to_drop:
        del retrieved_record[key]
    return retrieved_record


def get_md_from_sem_scholar(record):
    if is_complete_metadata_source(record):
        return record

    try:
        search_api_url = \
            'https://api.semanticscholar.org/graph/v1/paper/search?query='
        url = search_api_url + record.get('title', '').replace(' ', '+')
        headers = {'user-agent': f'{__name__} (mailto:{EMAIL})'}
        ret = requests.get(url, headers=headers)

        data = json.loads(ret.text)
        items = data['data']
        if len(items) == 0:
            return record
        if 'paperId' not in items[0]:
            return record

        paper_id = items[0]['paperId']
        record_retrieval_url = \
            'https://api.semanticscholar.org/v1/paper/' + paper_id
        ret_ent = requests.get(record_retrieval_url, headers=headers)
        item = json.loads(ret_ent.text)
        retrieved_record = sem_scholar_json_to_record(item, record)

        red_record_copy = record.copy()
        for key in ['volume', 'number', 'number', 'pages']:
            if key in red_record_copy:
                del red_record_copy[key]

        similarity = dedupe.get_record_similarity(red_record_copy,
                                                  retrieved_record.copy())
        logging.debug(f'scholar similarity: {similarity}')
        if similarity > 0.9:
            for key, val in retrieved_record.items():
                record[key] = val
            record.update(metadata_source='SEMANTIC_SCHOLAR')

    except KeyError:
        pass

    except UnicodeEncodeError:
        logging.error(
            'UnicodeEncodeError - this needs to be fixed at some time')
        pass
    except requests.exceptions.ConnectionError:
        logging.error('requests.exceptions.ConnectionError '
                      'in get_md_from_sem_scholar')
        pass
    return record


def get_dblp_venue(venue_string):
    venue = venue_string
    api_url = 'https://dblp.org/search/venue/api?q='
    url = api_url + venue_string.replace(' ', '+') + '&format=json'
    headers = {'user-agent': f'{__name__} (mailto:{EMAIL})'}
    try:
        ret = requests.get(url, headers=headers)
        data = json.loads(ret.text)

        hits = data['result']['hits']['hit']
        for hit in hits:
            if f'/{venue_string.lower()}/' in hit['info']['url']:
                venue = hit['info']['venue']
                break

        venue = re.sub(r' \(.*?\)', '', venue)
    except requests.exceptions.ConnectionError:
        logging.info('requests.exceptions.ConnectionError in get_dblp_venue()')
        pass
    return venue


def dblp_json_to_record(item):
    # To test in browser:
    # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json
    retrieved_record = {}
    if 'Journal Articles' == item['type']:
        retrieved_record['ENTRYTYPE'] = 'article'
        lpos = item['key'].find('/')+1
        rpos = item['key'].rfind('/')
        jour = item['key'][lpos:rpos]
        retrieved_record['journal'] = get_dblp_venue(jour)
    if 'Conference and Workshop Papers' == item['type']:
        retrieved_record['ENTRYTYPE'] = 'inproceedings'
        retrieved_record['booktitle'] = get_dblp_venue(item['venue'])

    if 'volume' in item:
        retrieved_record['volume'] = item['volume']
    if 'number' in item:
        retrieved_record['number'] = item['number']
    if 'pages' in item:
        retrieved_record['pages'] = item['pages']

    if 'author' in item['authors']:
        authors = [author for author in item['authors']['author']
                   if isinstance(author, dict)]
        authors = [x['text'] for x in authors if 'text' in x]
        author_string = ' and '.join(authors)
        author_string = format_author_field(author_string)
        retrieved_record['author'] = author_string

    if 'doi' in item:
        retrieved_record['doi'] = item['doi']
    if 'url' not in item:
        retrieved_record['url'] = item['ee']

    return retrieved_record


def get_md_from_dblp(record):
    if is_complete_metadata_source(record):
        return record

    try:
        api_url = 'https://dblp.org/search/publ/api?q='
        url = api_url + \
            record.get('title', '').replace(' ', '+') + '&format=json'
        headers = {'user-agent': f'{__name__}  (mailto:{EMAIL})'}
        ret = requests.get(url, headers=headers)

        data = json.loads(ret.text)
        hits = data['result']['hits']['hit']
        for hit in hits:
            item = hit['info']

            retrieved_record = dblp_json_to_record(item)

            similarity = dedupe.get_record_similarity(record.copy(),
                                                      retrieved_record.copy())
            logging.debug(f'dblp similarity: {similarity}')
            if similarity > 0.90:
                for key, val in retrieved_record.items():
                    record[key] = val
                record['dblp_key'] = 'https://dblp.org/rec/' + item['key']
                record.update(metadata_source='DBLP')

    except KeyError:
        pass
    except UnicodeEncodeError:
        logging.error(
            'UnicodeEncodeError - this needs to be fixed at some time')
        pass
    except requests.exceptions.ConnectionError:
        logging.error('requests.exceptions.ConnectionError in crossref_query')
        return record
    return record


# https://www.crossref.org/blog/dois-and-matching-regular-expressions/
doi_regex = re.compile(r'10\.\d{4,9}/[-._;/:A-Za-z0-9]*')


def retrieve_doi_metadata(record):
    if 'doi' not in record:
        return record

    # for testing:
    # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
    # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

    try:
        url = 'http://dx.doi.org/' + record['doi']
        headers = {'accept': 'application/vnd.citationstyles.csl+json'}
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            logging.info(f' {record["ID"]}'.ljust(PAD, ' ') + 'metadata for ' +
                         f'doi  {record["doi"]} not (yet) available')
            return record

        # For exceptions:
        orig_record = record.copy()

        retrieved_json = json.loads(r.text)
        retrieved_record = json_to_record(retrieved_json)
        for key, val in retrieved_record.items():
            record[key] = val

    # except IndexError:
    # except json.decoder.JSONDecodeError:
    # except TypeError:
    except requests.exceptions.ConnectionError:
        logging.error(f'ConnectionError: {record["ID"]}')
        return orig_record
        pass
    return record


def get_md_from_urls(record):
    if is_complete_metadata_source(record):
        return record

    url = record.get('url', record.get('fulltext', 'NA'))
    if 'NA' != url:
        try:
            headers = {'user-agent': f'{__name__}  (mailto:{EMAIL})'}
            ret = requests.get(url, headers=headers)
            res = re.findall(doi_regex, ret.text)
            if res:
                if len(res) == 1:
                    ret_doi = res[0]
                else:
                    counter = collections.Counter(res)
                    ret_doi = counter.most_common(1)[0][0]

                if not ret_doi:
                    return record

                # TODO: check multiple dois if applicable
                retrieved_record = {'doi': ret_doi, 'ID': record['ID']}
                retrieved_record = retrieve_doi_metadata(retrieved_record)
                similarity = \
                    dedupe.get_record_similarity(
                        record.copy(), retrieved_record)
                if similarity > 0.95:
                    for key, val in retrieved_record.items():
                        record[key] = val

                    logging.info('Retrieved metadata based on doi from'
                                 f' website: {record["doi"]}')
                    record.update(metadata_source='LINKED_URL')

        except requests.exceptions.ConnectionError:
            return record
            pass
        except Exception as e:
            print(f'exception: {e}')
            return record
            pass
    return record


# Based on https://en.wikipedia.org/wiki/BibTeX
record_field_requirements = \
    {'article': ['author', 'title', 'journal', 'year', 'volume', 'number'],
     'inproceedings': ['author', 'title', 'booktitle', 'year'],
     'incollection': ['author', 'title', 'booktitle', 'publisher', 'year'],
     'inbook': ['author', 'title', 'chapter', 'publisher', 'year'],
     'book': ['author', 'title', 'publisher', 'year'],
     'phdthesis': ['author', 'title', 'school', 'year'],
     'masterthesis': ['author', 'title', 'school', 'year'],
     'techreport': ['author', 'title', 'institution', 'year'],
     'unpublished': ['title', 'author', 'year']}

# book, inbook: author <- editor


def missing_fields(record):
    missing_fields = []
    if record['ENTRYTYPE'] in record_field_requirements.keys():
        reqs = record_field_requirements[record['ENTRYTYPE']]
        missing_fields = [x for x in reqs if x not in record.keys()]
    else:
        missing_fields = ['no field requirements defined']
    return missing_fields


def is_complete(record):
    sufficiently_complete = False
    if record['ENTRYTYPE'] in record_field_requirements.keys():
        if len(missing_fields(record)) == 0:
            sufficiently_complete = True
    return sufficiently_complete


def is_complete_metadata_source(record):
    # Note: metadata_source is set at the end of each procedure
    # that completes/corrects metadata based on an external source
    return 'metadata_source' in record


record_field_inconsistencies = \
    {'article': ['booktitle'],
     'inproceedings': ['volume', 'issue', 'number', 'journal'],
     'incollection': [],
     'inbook': ['journal'],
     'book': ['volume', 'issue', 'number', 'journal'],
     'phdthesis': ['volume', 'issue', 'number', 'journal', 'booktitle'],
     'masterthesis': ['volume', 'issue', 'number', 'journal', 'booktitle'],
     'techreport': ['volume', 'issue', 'number', 'journal', 'booktitle'],
     'unpublished': ['volume', 'issue', 'number', 'journal', 'booktitle']}


def get_inconsistencies(record):
    inconsistent_fields = []
    if record['ENTRYTYPE'] in record_field_inconsistencies.keys():
        incons_fields = record_field_inconsistencies[record['ENTRYTYPE']]
        inconsistent_fields = [x for x in incons_fields if x in record]
    # Note: a thesis should be single-authored
    if 'thesis' in record['ENTRYTYPE'] and ' and ' in record.get('author', ''):
        inconsistent_fields.append('author')
    return inconsistent_fields


def has_inconsistent_fields(record):
    found_inconsistencies = False
    if record['ENTRYTYPE'] in record_field_inconsistencies.keys():
        inconsistencies = get_inconsistencies(record)
        if inconsistencies:
            found_inconsistencies = True
    return found_inconsistencies


def get_incomplete_fields(record):
    incomplete_fields = []
    for key in record.keys():
        if key in ['title', 'journal', 'booktitle', 'author']:
            if record[key].endswith('...') or record[key].endswith('…'):
                incomplete_fields.append(key)
    if record.get('author', '').endswith('and others'):
        incomplete_fields.append('author')
    return incomplete_fields


def has_incomplete_fields(record):
    if len(get_incomplete_fields(record)) > 0:
        return True
    return False


fields_to_keep = [
    'ID', 'ENTRYTYPE',
    'author', 'year', 'title',
    'journal', 'booktitle', 'series',
    'volume', 'number', 'pages', 'doi',
    'abstract', 'school',
    'editor', 'book-group-author',
    'book-author', 'keywords', 'file',
    'rev_status', 'md_status', 'pdf_status',
    'fulltext', 'origin',
    'dblp_key', 'sem_scholar_id',
    'url', 'metadata_source'
]
fields_to_drop = [
    'type', 'organization',
    'issn', 'isbn', 'note',
    'unique-id', 'month', 'researcherid-numbers',
    'orcid-numbers', 'eissn', 'article-number',
    'publisher', 'author_keywords', 'source',
    'affiliation', 'document_type', 'art_number',
    'address', 'language', 'doc-delivery-number',
    'da', 'usage-count-last-180-days', 'usage-count-since-2013',
    'doc-delivery-number', 'research-areas',
    'web-of-science-categories', 'number-of-cited-references',
    'times-cited', 'journal-iso', 'oa', 'keywords-plus',
    'funding-text', 'funding-acknowledgement', 'day',
    'related', 'bibsource', 'timestamp', 'biburl'
]


def drop_fields(record):
    for key in list(record):
        if 'NA' == record[key]:
            del record[key]
        if(key not in fields_to_keep):
            record.pop(key)
            # warn if fields are dropped that are not in fields_to_drop
            if key not in fields_to_drop:
                logging.info(f'Dropped {key} field')
    return record


def log_notifications(record, unprepared_record):
    change = 1 - dedupe.get_record_similarity(record.copy(), unprepared_record)
    if change > 0.1:
        logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                     f'Change score: {round(change, 2)}')

    if not (is_complete(record) or is_complete_metadata_source(record)):
        logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                     f'{str(record["ENTRYTYPE"]).title()} '
                     f'missing {missing_fields(record)}')
    if has_inconsistent_fields(record):
        logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                     f'{str(record["ENTRYTYPE"]).title()} '
                     f'with {get_inconsistencies(record)} field(s)'
                     ' (inconsistent')
    if has_incomplete_fields(record):
        logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                     f'Incomplete fields {get_incomplete_fields(record)}')
    return


def remove_nicknames(record):
    if 'author' in record:
        # Replace nicknames in parentheses
        record['author'] = re.sub(r'\([^)]*\)', '', record['author'])
        record['author'] = record['author'].replace('  ', ' ')
    return record


def prepare(record):
    global current_batch_counter

    if 'imported' != record['md_status']:
        return record

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return record
        else:
            current_batch_counter.value += 1

    # # Note: we require (almost) perfect matches for the scripts.
    # # Cases with higher dissimilarity will be handled in the man_prep.py
    prep_scripts = {'correct_recordtype': correct_recordtype,
                    'homogenize_record': homogenize_record,
                    'apply_local_rules': apply_local_rules,
                    'apply_crowd_rules': apply_crowd_rules,
                    'get_md_from_doi': get_md_from_doi,
                    'get_md_from_crossref': get_md_from_crossref,
                    'get_md_from_dblp': get_md_from_dblp,
                    'get_md_from_sem_scholar': get_md_from_sem_scholar,
                    'get_md_from_urls': get_md_from_urls,
                    'remove_nicknames': remove_nicknames,
                    }

    unprepared_record = record.copy()
    short_form = record.copy()
    short_form = drop_fields(short_form)
    logging.info(f'prepare({record["ID"]})' +
                 f' started with: \n{pp.pformat(short_form)}\n\n')
    for prep_script in prep_scripts:
        prior = record.copy()
        logging.debug(f'{prep_script}({record["ID"]}) called')
        record = prep_scripts[prep_script](record)
        diffs = list(dictdiffer.diff(prior, record))
        if diffs:
            logging.info(f'{prep_script}({record["ID"]}) changed:'
                         f' \n{pp.pformat(diffs)}\n')
        else:
            logging.debug(f'{prep_script} changed: -')

    if (is_complete(record) or is_complete_metadata_source(record)) and \
            not has_inconsistent_fields(record) and \
            not has_incomplete_fields(record):
        record = drop_fields(record)
        record.update(md_status='prepared')
    else:
        # if 'metadata_source' in record:
        #     del record['metadata_source']
        log_notifications(record, unprepared_record)
        record.update(md_status='needs_manual_preparation')

    return record


def set_stats_beginning(bib_db):
    global prepared
    global need_manual_prep
    prepared = len([x for x in bib_db.entries
                    if 'prepared' == x.get('md_status', 'NA')])
    need_manual_prep = \
        len([x for x in bib_db.entries
            if 'needs_manual_preparation' == x.get('md_status', 'NA')])
    return


def print_stats_end(bib_db):
    global prepared
    global need_manual_prep
    prepared = len([x for x in bib_db.entries
                    if 'prepared' == x.get('md_status', 'NA')]) - prepared
    need_manual_prep = \
        len([x for x in bib_db.entries
            if 'needs_manual_preparation' == x.get('md_status', 'NA')]) \
        - need_manual_prep
    if prepared > 0:
        logging.info(f'Summary: Prepared {prepared} records')
    if need_manual_prep > 0:
        logging.info(f'Summary: Marked {need_manual_prep} records ' +
                     'for manual preparation')
    return


def reorder_log(IDs):
    # https://docs.python.org/3/howto/logging-cookbook.html
    # #logging-to-a-single-file-from-multiple-processes
    firsts = []
    with open('report.log') as r:
        items = []
        item = ''
        for line in r.readlines():
            if any(x in line for x in ['[INFO] Prepare',
                                       '[INFO] Completed preparation ',
                                       '[INFO] Batch size',
                                       '[INFO] Summary: Prepared',
                                       '[INFO] Further instructions ',
                                       '[INFO] To reset the metdatata']):
                firsts.append(line)
                continue
            if re.search(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ', line):
                if item != '':
                    item = item.replace('\n\n', '\n').replace('\n\n', '\n')
                    items.append(item)
                    item = ''
                item = line
            else:
                item = item + line
        items.append(item.replace('\n\n', '\n').replace('\n\n', '\n'))

    ordered_items = ''
    consumed_items = []
    for ID in IDs:
        for item in items:
            # if f'({ID})' in item:
            if f'({ID})' in item:
                formatted_item = item
                if '] prepare(' in formatted_item:
                    formatted_item = f'\n\n{formatted_item}'
                ordered_items = ordered_items + formatted_item
                consumed_items.append(item)

    for x in consumed_items:
        items.remove(x)

    ordered_items = ''.join(firsts) + '\nDetailed report\n\n' + \
        ordered_items.lstrip('\n') + ''.join(items)
    with open('report.log', 'w') as f:
        f.write(ordered_items)
    return


def reset(bib_db, id):
    record = [x for x in bib_db.entries if x['ID'] == id]
    if len(record) == 0:
        logging.info(f'record with ID {record["ID"]} not found')
        return
    # Note: the case len(record) > 1 should not occur.
    record = record[0]
    if 'prepared' != record['md_status']:
        logging.error(f'{id}: md_status must be prepared '
                      f'(is {record["md_status"]})')
        return

    origins = record['origin'].split(';')

    repo = git.Repo()
    revlist = (
        ((commit.tree / MAIN_REFERENCES).data_stream.read())
        for commit in repo.iter_commits(paths=MAIN_REFERENCES)
    )
    for filecontents in list(revlist):
        prior_bib_db = bibtexparser.loads(filecontents)
        for e in prior_bib_db.entries:
            if 'imported' == e['md_status'] and \
                    any(o in e['origin'] for o in origins):
                e.update(md_status='needs_manual_preparation')
                logging.info(f'reset({record["ID"]}) to\n{pp.pformat(e)}\n\n')
                record.update(e)
                break
    return


def main(bib_db, repo, reset_ids=None, reprocess=False, keep_ids=False):
    saved_args = locals()
    if not reset_ids:
        del saved_args['reset_ids']
    if not reprocess:
        del saved_args['reprocess']
    if not keep_ids:
        del saved_args['keep_ids']
    global prepared
    global need_manual_prep
    global PAD
    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)
    prior_ids = [x['ID'] for x in bib_db.entries]

    process.check_delay(bib_db, min_status_requirement='md_imported')
    utils.reset_log()

    if reset_ids:
        for reset_id in reset_ids:
            reset(bib_db, reset_id)
        utils.save_bib_file(bib_db, MAIN_REFERENCES)
        repo.index.add([MAIN_REFERENCES])
        utils.create_commit(repo, '⚙️ Reset metadata for manual preparation')
        return

    # Note: resetting needs_manual_preparation to imported would also be
    # consistent with the check7valid_transitions because it will either
    # transition to prepared or to needs_manual_preparation
    if reprocess:
        for record in bib_db.entries:
            if 'needs_manual_preparation' == record['md_status']:
                record['md_status'] = 'imported'

    logging.info('Prepare')
    logging.info(f'Batch size: {BATCH_SIZE}')

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logging.info('Continuing batch preparation started earlier')

        set_stats_beginning(bib_db)

        pool = mp.Pool(repo_setup.config['CPUS'])
        bib_db.entries = pool.map(prepare, bib_db.entries)
        pool.close()
        pool.join()

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        if batch_end > 0:
            logging.info('Completed preparation batch '
                         f'(records {batch_start} to {batch_end})')

            if keep_ids:
                bib_db = utils.set_IDs(bib_db)

            utils.save_bib_file(bib_db, MAIN_REFERENCES)
            repo.index.add([MAIN_REFERENCES])

            print_stats_end(bib_db)
            logging.info('To reset the metdatata of records, use '
                         'review_template prepare --reset-ID [ID1,ID2]')
            logging.info('Further instructions are available in the '
                         'documentation (TODO: link)')

            # Multiprocessing mixes logs of different records.
            # For better readability:
            reorder_log(prior_ids)

            in_process = utils.create_commit(repo,
                                             '⚙️ Prepare records',
                                             saved_args)

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logging.info('No additional records to prepare')
            break

    print()

    return bib_db


@click.command()
def cli():
    repo = git.Repo()
    bib_db = utils.load_main_refs(mod_check=True, init=False)
    main(bib_db, repo)
    return 0


if __name__ == '__main__':
    main()
