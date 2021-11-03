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

BATCH_SIZE = repo_setup.config['BATCH_SIZE']
EMAIL = repo_setup.config['EMAIL']
pp = pprint.PrettyPrinter(indent=4, width=140)
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


def correct_entrytype(entry):

    conf_strings = [
        'proceedings',
        'conference',
    ]

    for i, row in LOCAL_CONFERENCE_ABBREVIATIONS.iterrows():
        conf_strings.append(row['abbreviation'].lower())
        conf_strings.append(row['conference'].lower())

    # Consistency checks
    if 'journal' in entry:
        if any(x in entry['journal'].lower() for x in conf_strings):
            entry.update(booktitle=entry['journal'])
            entry.update(ENTRYTYPE='inproceedings')
            del entry['journal']
    if 'booktitle' in entry:
        if any(x in entry['booktitle'].lower() for x in conf_strings):
            entry.update(ENTRYTYPE='inproceedings')

    if 'dissertation' in entry.get('fulltext', 'NA').lower() and \
            entry['ENTRYTYPE'] != 'phdthesis':
        prior_e_type = entry['ENTRYTYPE']
        entry.update(ENTRYTYPE='phdthesis')
        logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                     f'Set from {prior_e_type} to phdthesis '
                     '("dissertation" in fulltext link)')
        # TODO: if school is not set: using named entity recognition or
        # following links: detect the school and set the field

    if 'thesis' in entry.get('fulltext', 'NA').lower() and \
            entry['ENTRYTYPE'] != 'phdthesis':
        prior_e_type = entry['ENTRYTYPE']
        entry.update(ENTRYTYPE='phdthesis')
        logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                     f'Set from {prior_e_type} to phdthesis '
                     '("thesis" in fulltext link)')
        # TODO: if school is not set: using named entity recognition or
        # following links: detect the school and set the field

    # TODO: create a warning if any conference strings (ecis, icis, ..)
    # as stored in CONFERENCE_ABBREVIATIONS is in an article/book

    # Journal articles should not have booktitles/series set.
    if 'article' == entry['ENTRYTYPE']:
        if 'booktitle' in entry:
            if 'journal' not in entry:
                entry.update(journal=entry['booktitle'])
                del entry['booktitle']
        if 'series' in entry:
            if 'journal' not in entry:
                entry.update(journal=entry['series'])
                del entry['series']

    if 'book' == entry['ENTRYTYPE']:
        if 'series' in entry:
            if any(x in entry['series'].lower() for x in conf_strings):
                conf_name = entry['series']
                del entry['series']
                entry.update(booktitle=conf_name)
                entry.update(ENTRYTYPE='inproceedings')

    if 'article' == entry['ENTRYTYPE']:
        if 'journal' not in entry:
            if 'series' in entry:
                journal_string = entry['series']
                entry.update(journal=journal_string)
                del entry['series']

    return entry


def homogenize_entry(entry):

    fields_to_process = [
        'author', 'year', 'title',
        'journal', 'booktitle', 'series',
        'volume', 'issue', 'pages', 'doi',
        'abstract'
    ]
    for field in fields_to_process:
        if field in entry:
            entry[field] = entry[field].replace('\n', ' ')\
                .rstrip().lstrip()\
                .replace('{', '').replace('}', '')

    if 'author' in entry:
        # DBLP appends identifiers to non-unique authors
        entry.update(author=str(re.sub(r'[0-9]{4}', '', entry['author'])))

        # fix name format
        if (1 == len(entry['author'].split(' ')[0])) or \
                (', ' not in entry['author']):
            entry.update(author=format_author_field(entry['author']))

    if 'title' in entry:
        entry.update(title=re.sub(r'\s+', ' ', entry['title']).rstrip('.'))
        entry.update(title=title_if_mostly_upper_case(entry['title']))

    if 'booktitle' in entry:
        entry.update(booktitle=title_if_mostly_upper_case(entry['booktitle']))

        stripped_btitle = re.sub(r'\d{4}', '', entry['booktitle'])
        stripped_btitle = re.sub(r'\d{1,2}th', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}nd', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}rd', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}st', '', stripped_btitle)
        stripped_btitle = re.sub(r'\([A-Z]{3,6}\)', '', stripped_btitle)
        stripped_btitle = stripped_btitle.replace('Proceedings of the', '')\
            .replace('Proceedings', '')
        entry.update(booktitle=stripped_btitle)

    if 'journal' in entry:
        entry.update(journal=title_if_mostly_upper_case(entry['journal']))

    if 'pages' in entry:
        entry.update(pages=unify_pages_field(entry['pages']))
        if not re.match(r'^\d*$', entry['pages']) and \
                not re.match(r'^\d*--\d*$', entry['pages']) and\
                not re.match(r'^[xivXIV]*--[xivXIV]*$', entry['pages']):
            logging.info(f' {entry["ID"]}:'.ljust(PAD, ' ') +
                         f'Unusual pages: {entry["pages"]}')

    if 'doi' in entry:
        entry.update(doi=entry['doi'].replace('http://dx.doi.org/', ''))

    if 'issue' not in entry and 'number' in entry:
        entry.update(issue=entry['number'])
        del entry['number']

    return entry


LOCAL_JOURNAL_ABBREVIATIONS, \
    LOCAL_JOURNAL_VARIATIONS, \
    LOCAL_CONFERENCE_ABBREVIATIONS = \
    retrieve_local_resources()


def apply_local_rules(entry):

    if 'journal' in entry:
        for i, row in LOCAL_JOURNAL_ABBREVIATIONS.iterrows():
            if row['abbreviation'].lower() == entry['journal'].lower():
                entry.update(journal=row['journal'])

        for i, row in LOCAL_JOURNAL_VARIATIONS.iterrows():
            if row['variation'].lower() == entry['journal'].lower():
                entry.update(journal=row['journal'])

    if 'booktitle' in entry:
        for i, row in LOCAL_CONFERENCE_ABBREVIATIONS.iterrows():
            if row['abbreviation'].lower() == entry['booktitle'].lower():
                entry.update(booktitle=row['conference'])

    return entry


CR_JOURNAL_ABBREVIATIONS, \
    CR_JOURNAL_VARIATIONS, \
    CR_CONFERENCE_ABBREVIATIONS = \
    retrieve_crowd_resources()


def apply_crowd_rules(entry):

    if 'journal' in entry:
        for i, row in CR_JOURNAL_ABBREVIATIONS.iterrows():
            if row['abbreviation'].lower() == entry['journal'].lower():
                entry.update(journal=row['journal'])

        for i, row in CR_JOURNAL_VARIATIONS.iterrows():
            if row['variation'].lower() == entry['journal'].lower():
                entry.update(journal=row['journal'])

    if 'booktitle' in entry:
        for i, row in CR_CONFERENCE_ABBREVIATIONS.iterrows():
            if row['abbreviation'].lower() == entry['booktitle'].lower():
                entry.update(booktitle=row['conference'])

    return entry


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
            '{last} {suffix}, {first} ({nickname}) {middle}'
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


def get_container_title(entry):
    container_title = 'NA'
    if 'ENTRYTYPE' not in entry:
        container_title = entry.get('journal', entry.get('booktitle', 'NA'))
    else:
        if 'article' == entry['ENTRYTYPE']:
            container_title = entry.get('journal', 'NA')
        if 'inproceedings' == entry['ENTRYTYPE']:
            container_title = entry.get('booktitle', 'NA')
        if 'book' == entry['ENTRYTYPE']:
            container_title = entry.get('title', 'NA')
        if 'inbook' == entry['ENTRYTYPE']:
            container_title = entry.get('booktitle', 'NA')
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


def get_md_from_doi(entry):
    if 'doi' not in entry:
        return entry

    entry = retrieve_doi_metadata(entry)
    entry.update(metadata_source='DOI.ORG')

    return entry


def json_to_entry(item):
    # Note: the format differst between crossref and doi.org

    entry = {}

    if 'title' in item:
        retrieved_title = item['title']
        if isinstance(retrieved_title, list):
            retrieved_title = retrieved_title[0]
        retrieved_title = \
            re.sub(r'\s+', ' ', str(retrieved_title)).replace('\n', ' ')
        entry.update(title=retrieved_title)

    container_title = None
    if 'container-title' in item:
        container_title = item['container-title']
        if isinstance(container_title, list):
            container_title = container_title[0]

    if 'type' in item:
        if 'journal-article' == item.get('type', 'NA'):
            entry.update(ENTRYTYPE='article')
            if container_title is not None:
                entry.update(journal=container_title)
        if 'proceedings-article' == item.get('type', 'NA'):
            entry.update(ENTRYTYPE='inproceedings')
            if container_title is not None:
                entry.update(booktitle=container_title)
        if 'book' == item.get('type', 'NA'):
            entry.update(ENTRYTYPE='book')
            if container_title is not None:
                entry.update(series=container_title)

    if 'DOI' in item:
        entry.update(doi=item['DOI'])

    authors = [f'{author["family"]}, {author.get("given", "")}'
               for author in item['author']
               if 'family' in author]
    authors_string = ' and '.join(authors)
    # authors_string = format_author_field(authors_string)
    entry.update(author=authors_string)

    try:
        if 'published-print' in item:
            date_parts = item['published-print']['date-parts']
            entry.update(year=str(date_parts[0][0]))
        elif 'published-online' in item:
            date_parts = item['published-online']['date-parts']
            entry.update(year=str(date_parts[0][0]))
    except KeyError:
        pass

    retrieved_pages = item.get('page', '')
    if retrieved_pages != '':
        # DOI data often has only the first page.
        if not entry.get('pages', 'no_pages') in retrieved_pages \
                and '-' in retrieved_pages:
            entry.update(pages=unify_pages_field(str(retrieved_pages)))
    retrieved_volume = item.get('volume', '')
    if not retrieved_volume == '':
        entry.update(volume=str(retrieved_volume))

    retrieved_issue = item.get('issue', '')
    if 'journal-issue' in item:
        if 'issue' in item['journal-issue']:
            retrieved_issue = item['journal-issue']['issue']
    if not retrieved_issue == '':
        entry.update(issue=str(retrieved_issue))

    if 'abstract' in item:
        retrieved_abstract = item['abstract']
        if not retrieved_abstract == '':
            retrieved_abstract = \
                re.sub(r'<\/?jats\:[^>]*>', ' ', retrieved_abstract)
            retrieved_abstract = re.sub(r'\s+', ' ', retrieved_abstract)
            retrieved_abstract = str(retrieved_abstract).replace('\n', '')\
                .lstrip().rstrip()
            entry.update(abstract=retrieved_abstract)
    return entry


def crossref_query(entry):
    # https://github.com/CrossRef/rest-api-doc
    api_url = 'https://api.crossref.org/works?'
    bibliographic = entry['title'] + ' ' + entry.get('year', '')
    bibliographic = bibliographic.replace('...', '').replace('…', '')
    container_title = get_container_title(entry)
    container_title = container_title.replace('...', '').replace('…', '')
    author_string = entry['author'].replace('...', '').replace('…', '')
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
        most_similar_entry = None
        for item in items:
            if 'title' not in item:
                continue

            retrieved_entry = json_to_entry(item)

            title_similarity = fuzz.partial_ratio(
                retrieved_entry['title'].lower(),
                entry['title'].lower(),
            )
            container_similarity = fuzz.partial_ratio(
                get_container_title(retrieved_entry).lower(),
                get_container_title(entry).lower(),
            )
            weights = [0.6, 0.4]
            similarities = [title_similarity, container_similarity]

            similarity = sum(similarities[g] * weights[g]
                             for g in range(len(similarities)))
            # logging.debug(f'entry: {pp.pformat(entry)}')
            # logging.debug(f'similarities: {similarities}')
            # logging.debug(f'similarity: {similarity}')

            if most_similar < similarity:
                most_similar = similarity
                most_similar_entry = retrieved_entry
    except requests.exceptions.ConnectionError:
        logging.error('requests.exceptions.ConnectionError in crossref_query')
        return None

    return most_similar_entry


def get_md_from_crossref(entry):
    if ('title' not in entry) or ('doi' in entry):
        return entry

    logging.debug(f'get_md_from_crossref({entry["ID"]})')
    MAX_RETRIES_ON_ERROR = 3
    # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
    if len(entry['title']) > 35:
        try:

            retrieved_entry = crossref_query(entry)
            retries = 0
            while not retrieved_entry and retries < MAX_RETRIES_ON_ERROR:
                retries += 1
                retrieved_entry = crossref_query(entry)

            if retrieved_entry is None:
                return entry

            similarity = dedupe.get_entry_similarity(entry.copy(),
                                                     retrieved_entry.copy())
            logging.debug(f'crossref similarity: {similarity}')
            if similarity > 0.90:
                for key, val in retrieved_entry.items():
                    entry[key] = val
                entry.update(metadata_source='CROSSREF')

        except KeyboardInterrupt:
            sys.exit()
    return entry


def sem_scholar_json_to_entry(item, entry):
    retrieved_entry = {}
    if 'authors' in item:
        authors_string = ' and '.join([author['name']
                                       for author in item['authors']
                                       if 'name' in author])
        authors_string = format_author_field(authors_string)
        retrieved_entry.update(author=authors_string)
    if 'abstract' in item:
        retrieved_entry.update(abstract=item['abstract'])
    if 'doi' in item:
        retrieved_entry.update(doi=item['doi'])
    if 'title' in item:
        retrieved_entry.update(title=item['title'])
    if 'year' in item:
        retrieved_entry.update(year=item['year'])
    # Note: semantic scholar does not provide data on the type of venue.
    # we therefore use the original entrytype
    if 'venue' in item:
        if 'journal' in entry:
            retrieved_entry.update(journal=item['venue'])
        if 'booktitle' in entry:
            retrieved_entry.update(booktitle=item['venue'])
    if 'url' in item:
        retrieved_entry.update(sem_scholar_id=item['url'])

    keys_to_drop = []
    for key, value in retrieved_entry.items():
        retrieved_entry[key] =  \
            str(value).replace('\n', ' ').lstrip().rstrip()
        if value in ['', 'None'] or value is None:
            keys_to_drop.append(key)
    for key in keys_to_drop:
        del retrieved_entry[key]
    return retrieved_entry


def get_md_from_sem_scholar(entry):

    try:
        search_api_url = \
            'https://api.semanticscholar.org/graph/v1/paper/search?query='
        url = search_api_url + entry.get('title', '').replace(' ', '+')
        headers = {'user-agent': f'{__name__} (mailto:{EMAIL})'}
        ret = requests.get(url, headers=headers)

        data = json.loads(ret.text)
        items = data['data']
        if len(items) == 0:
            return entry
        if 'paperId' not in items[0]:
            return entry

        paper_id = items[0]['paperId']
        entry_retrieval_url = \
            'https://api.semanticscholar.org/v1/paper/' + paper_id
        ret_ent = requests.get(entry_retrieval_url, headers=headers)
        item = json.loads(ret_ent.text)
        retrieved_entry = sem_scholar_json_to_entry(item, entry)

        red_entry_copy = entry.copy()
        for key in ['volume', 'number', 'issue', 'pages']:
            if key in red_entry_copy:
                del red_entry_copy[key]

        similarity = dedupe.get_entry_similarity(red_entry_copy,
                                                 retrieved_entry.copy())
        logging.debug(f'scholar similarity: {similarity}')
        if similarity > 0.9:
            for key, val in retrieved_entry.items():
                entry[key] = val
            entry.update(metadata_source='SEMANTIC_SCHOLAR')

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
    return entry


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


def dblp_json_to_entry(item):
    # To test in browser:
    # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json
    retrieved_entry = {}
    if 'Journal Articles' == item['type']:
        retrieved_entry['ENTRYTYPE'] = 'article'
        lpos = item['key'].find('/')+1
        rpos = item['key'].rfind('/')
        jour = item['key'][lpos:rpos]
        retrieved_entry['journal'] = get_dblp_venue(jour)
    if 'Conference and Workshop Papers' == item['type']:
        retrieved_entry['ENTRYTYPE'] = 'inproceedings'
        retrieved_entry['booktitle'] = get_dblp_venue(item['venue'])

    if 'volume' in item:
        retrieved_entry['volume'] = item['volume']
    if 'number' in item:
        retrieved_entry['issue'] = item['number']
    if 'pages' in item:
        retrieved_entry['pages'] = item['pages']

    if 'author' in item['authors']:
        authors = [author for author in item['authors']['author']
                   if isinstance(author, dict)]
        authors = [x['text'] for x in authors if 'text' in x]
        author_string = ' and '.join(authors)
        author_string = format_author_field(author_string)
        retrieved_entry['author'] = author_string

    if 'doi' in item:
        retrieved_entry['doi'] = item['doi']
    if 'url' not in item:
        retrieved_entry['url'] = item['ee']

    return retrieved_entry


def get_md_from_dblp(entry):

    try:
        api_url = 'https://dblp.org/search/publ/api?q='
        url = api_url + \
            entry.get('title', '').replace(' ', '+') + '&format=json'
        headers = {'user-agent': f'{__name__}  (mailto:{EMAIL})'}
        ret = requests.get(url, headers=headers)

        data = json.loads(ret.text)
        hits = data['result']['hits']['hit']
        for hit in hits:
            item = hit['info']

            retrieved_entry = dblp_json_to_entry(item)

            similarity = dedupe.get_entry_similarity(entry.copy(),
                                                     retrieved_entry.copy())
            logging.debug(f'dblp similarity: {similarity}')
            if similarity > 0.90:
                for key, val in retrieved_entry.items():
                    entry[key] = val
                entry['dblp_key'] = 'https://dblp.org/rec/' + item['key']
                entry.update(metadata_source='DBLP')

    except KeyError:
        pass
    except UnicodeEncodeError:
        logging.error(
            'UnicodeEncodeError - this needs to be fixed at some time')
        pass
    except requests.exceptions.ConnectionError:
        logging.error('requests.exceptions.ConnectionError in crossref_query')
        return entry
    return entry


# https://www.crossref.org/blog/dois-and-matching-regular-expressions/
doi_regex = re.compile(r'10\.\d{4,9}/[-._;/:A-Za-z0-9]*')


def retrieve_doi_metadata(entry):
    if 'doi' not in entry:
        return entry

    # for testing:
    # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
    # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

    try:
        url = 'http://dx.doi.org/' + entry['doi']
        headers = {'accept': 'application/vnd.citationstyles.csl+json'}
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') + 'metadata for ' +
                         f'doi  {entry["doi"]} not (yet) available')
            return entry

        # For exceptions:
        orig_entry = entry.copy()

        retrieved_json = json.loads(r.text)
        retrieved_entry = json_to_entry(retrieved_json)
        for key, val in retrieved_entry.items():
            entry[key] = val

    # except IndexError:
    # except json.decoder.JSONDecodeError:
    # except TypeError:
    except requests.exceptions.ConnectionError:
        logging.error(f'ConnectionError: {entry["ID"]}')
        return orig_entry
        pass
    return entry


def get_md_from_urls(entry):

    url = entry.get('url', entry.get('fulltext', 'NA'))
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
                    return entry

                # TODO: check multiple dois if applicable
                retrieved_entry = {'doi': ret_doi, 'ID': entry['ID']}
                retrieved_entry = retrieve_doi_metadata(retrieved_entry)
                similarity = \
                    dedupe.get_entry_similarity(entry.copy(), retrieved_entry)
                if similarity > 0.95:
                    for key, val in retrieved_entry.items():
                        entry[key] = val

                    logging.info('Retrieved metadata based on doi from'
                                 f' website: {entry["doi"]}')
                    entry.update(metadata_source='LINKED_URL')

        except requests.exceptions.ConnectionError:
            return entry
            pass
        except Exception as e:
            print(f'exception: {e}')
            return entry
            pass
    return entry


# Based on https://en.wikipedia.org/wiki/BibTeX
entry_field_requirements = \
    {'article': ['author', 'title', 'journal', 'year', 'volume', 'issue'],
     'inproceedings': ['author', 'title', 'booktitle', 'year'],
     'incollection': ['author', 'title', 'booktitle', 'publisher', 'year'],
     'inbook': ['author', 'title', 'chapter', 'publisher', 'year'],
     'book': ['author', 'title', 'publisher', 'year'],
     'phdthesis': ['author', 'title', 'school', 'year'],
     'masterthesis': ['author', 'title', 'school', 'year'],
     'techreport': ['author', 'title', 'institution', 'year'],
     'unpublished': ['title', 'author', 'year']}

# book, inbook: author <- editor


def missing_fields(entry):
    missing_fields = []
    if entry['ENTRYTYPE'] in entry_field_requirements.keys():
        reqs = entry_field_requirements[entry['ENTRYTYPE']]
        missing_fields = [x for x in reqs if x not in entry.keys()]
    else:
        missing_fields = ['no field requirements defined']
    return missing_fields


def is_complete(entry):
    sufficiently_complete = False
    if entry['ENTRYTYPE'] in entry_field_requirements.keys():
        if len(missing_fields(entry)) == 0:
            sufficiently_complete = True
    return sufficiently_complete


def is_complete_metadata_source(entry):
    # Note: metadata_source is set at the end of each procedure
    # that completes/corrects metadata based on an external source
    return 'metadata_source' in entry


entry_field_inconsistencies = \
    {'article': ['booktitle'],
     'inproceedings': ['volume', 'issue', 'number', 'journal'],
     'incollection': [],
     'inbook': ['journal'],
     'book': ['volume', 'issue', 'number', 'journal'],
     'phdthesis': ['volume', 'issue', 'number', 'journal', 'booktitle'],
     'masterthesis': ['volume', 'issue', 'number', 'journal', 'booktitle'],
     'techreport': ['volume', 'issue', 'number', 'journal', 'booktitle'],
     'unpublished': ['volume', 'issue', 'number', 'journal', 'booktitle']}


def get_inconsistencies(entry):
    inconsistent_fields = []
    if entry['ENTRYTYPE'] in entry_field_inconsistencies.keys():
        incons_fields = entry_field_inconsistencies[entry['ENTRYTYPE']]
        inconsistent_fields = [x for x in incons_fields if x in entry]
    # Note: a thesis should be single-authored
    if 'thesis' in entry['ENTRYTYPE'] and ' and ' in entry.get('author', ''):
        inconsistent_fields.append('author')
    return inconsistent_fields


def has_inconsistent_fields(entry):
    found_inconsistencies = False
    if entry['ENTRYTYPE'] in entry_field_inconsistencies.keys():
        inconsistencies = get_inconsistencies(entry)
        if inconsistencies:
            found_inconsistencies = True
    return found_inconsistencies


def get_incomplete_fields(entry):
    incomplete_fields = []
    for key in entry.keys():
        if key in ['title', 'journal', 'booktitle', 'author']:
            if entry[key].endswith('...') or entry[key].endswith('…'):
                incomplete_fields.append(key)
    if entry.get('author', '').endswith('and others'):
        incomplete_fields.append('author')
    return incomplete_fields


def has_incomplete_fields(entry):
    if len(get_incomplete_fields(entry)) > 0:
        return True
    return False


fields_to_keep = [
    'ID', 'ENTRYTYPE',
    'author', 'year', 'title',
    'journal', 'booktitle', 'series',
    'volume', 'issue', 'pages', 'doi',
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
    'issn', 'isbn', 'note', 'number',
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


def drop_fields(entry):
    for key in list(entry):
        if 'NA' == entry[key]:
            del entry[key]
        if(key not in fields_to_keep):
            entry.pop(key)
            # warn if fields are dropped that are not in fields_to_drop
            if key not in fields_to_drop:
                logging.info(f'Dropped {key} field')
    return entry


def log_notifications(entry, unprepared_entry):
    change = 1 - dedupe.get_entry_similarity(entry.copy(), unprepared_entry)
    if change > 0.1:
        logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                     f'Change score: {round(change, 2)}')

    if not (is_complete(entry) or is_complete_metadata_source(entry)):
        logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                     f'{str(entry["ENTRYTYPE"]).title()} '
                     f'missing {missing_fields(entry)}')
    if has_inconsistent_fields(entry):
        logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                     f'{str(entry["ENTRYTYPE"]).title()} '
                     f'with {get_inconsistencies(entry)} field(s)'
                     ' (inconsistent')
    if has_incomplete_fields(entry):
        logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                     f'Incomplete fields {get_incomplete_fields(entry)}')
    return


def prepare(entry):
    global current_batch_counter

    if 'imported' != entry['md_status']:
        return entry

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return entry
        else:
            current_batch_counter.value += 1

    # # Note: we require (almost) perfect matches for the scripts.
    # # Cases with higher dissimilarity will be handled in the man_prep.py
    prep_scripts = {'correct_entrytype': correct_entrytype,
                    'homogenize_entry': homogenize_entry,
                    'apply_local_rules': apply_local_rules,
                    'apply_crowd_rules': apply_crowd_rules,
                    'get_md_from_doi': get_md_from_doi,
                    'get_md_from_crossref': get_md_from_crossref,
                    'get_md_from_dblp': get_md_from_dblp,
                    'get_md_from_sem_scholar': get_md_from_sem_scholar,
                    'get_md_from_urls': get_md_from_urls,
                    }

    unprepared_entry = entry.copy()
    logging.info(f'{entry["ID"]}'.ljust(PAD, ' ') +
                 f'start preparation: \n{pp.pformat(entry)}\n\n')
    for prep_script in prep_scripts:
        prior = entry.copy()
        logging.debug(f'{prep_script}({entry["ID"]}) called')
        entry = prep_scripts[prep_script](entry)
        diffs = list(dictdiffer.diff(prior, entry))
        if diffs:
            logging.info(f'{prep_script}({entry["ID"]}) changed:'
                         f' \n{pp.pformat(diffs)}\n')
        else:
            logging.debug(f'{prep_script} changed: -')
        if is_complete_metadata_source(entry):
            break

    if (is_complete(entry) or is_complete_metadata_source(entry)) and \
            not has_inconsistent_fields(entry) and \
            not has_incomplete_fields(entry):
        entry = drop_fields(entry)
        entry.update(md_status='prepared')
    else:
        # if 'metadata_source' in entry:
        #     del entry['metadata_source']
        log_notifications(entry, unprepared_entry)
        entry.update(md_status='needs_manual_preparation')

    return entry


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
        logging.info(f'Summary: Prepared {prepared} entries')
    if need_manual_prep > 0:
        logging.info(f'Summary: Marked {need_manual_prep} entries ' +
                     'for manual preparation')
    return


def main(bib_db, repo):
    global prepared
    global need_manual_prep
    global PAD
    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)

    process.check_delay(bib_db, min_status_requirement='md_imported')
    utils.reset_log()

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
                         f'(entries {batch_start} to {batch_end})')

            bib_db = utils.set_IDs(bib_db)

            MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
            utils.save_bib_file(bib_db, MAIN_REFERENCES)
            repo.index.add([MAIN_REFERENCES])

            print_stats_end(bib_db)
            logging.info('Instructions on resetting entries and analyzing '
                         'preparation steps available in the documentation '
                         '(link)')
            in_process = utils.create_commit(repo, '⚙️ Prepare records')

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logging.info('No additional entries to prepare')
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
