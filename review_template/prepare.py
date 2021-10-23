#! /usr/bin/env python
import collections
import json
import logging
import multiprocessing as mp
import os
import re
import sys
import time
import urllib

import git
import requests
from Levenshtein import ratio
from nameparser import HumanName

from review_template import dedupe
from review_template import process
from review_template import repo_setup
from review_template import utils

BATCH_SIZE = repo_setup.config['BATCH_SIZE']

prepared, need_manual_prep = 0, 0

current_batch_counter = mp.Value('i', 0)


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
        if any(
            conf_string in entry['journal'].lower()
            for conf_string in conf_strings
        ):
            # print('WARNING: conference string in journal field: ',
            #       entry['ID'],
            #       entry['journal'])
            entry.update(booktitle=entry['journal'])
            entry.update(ENTRYTYPE='inproceedings')
            del entry['journal']
    if 'booktitle' in entry:
        if any(
            conf_string in entry['booktitle'].lower()
            for conf_string in conf_strings
        ):
            entry.update(ENTRYTYPE='inproceedings')

    if 'dissertation' in entry.get('fulltext', 'NA').lower() and \
            entry['ENTRYTYPE'] != 'phdthesis':
        prior_e_type = entry['ENTRYTYPE']
        entry.update(ENTRYTYPE='phdthesis')
        logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                     f'Set from {prior_e_type} to phdthesis '
                     '("dissertation" in fulltext link)')
        # TODO: if school is not set: using named entity recognition or
        # following links: detect the school and set the field

    if 'thesis' in entry.get('fulltext', 'NA').lower() and \
            entry['ENTRYTYPE'] != 'phdthesis':
        prior_e_type = entry['ENTRYTYPE']
        entry.update(ENTRYTYPE='phdthesis')
        logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
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
            if any(
                conf_string in entry['series'].lower()
                for conf_string in conf_strings
            ):
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
                .rstrip()\
                .lstrip()\
                .replace('{', '')\
                .replace('}', '')

    if 'author' in entry:
        # DBLP appends identifiers to non-unique authors
        entry.update(author=str(re.sub(r'[0-9]{4}', '', entry['author'])))

        # fix name format
        if (1 == len(entry['author'].split(' ')[0])) or \
                (', ' not in entry['author']):
            entry.update(author=utils.format_author_field(entry['author']))

    if 'title' in entry:
        entry.update(title=re.sub(r'\s+', ' ', entry['title']).rstrip('.'))
        entry.update(title=utils.title_if_mostly_upper_case(entry['title']))

    if 'booktitle' in entry:
        entry.update(booktitle=utils.title_if_mostly_upper_case(
            entry['booktitle']))

        stripped_btitle = re.sub(r'\d{4}', '', entry['booktitle'])
        stripped_btitle = re.sub(r'\d{1,2}th', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}nd', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}rd', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}st', '', stripped_btitle)
        stripped_btitle = re.sub(r'\([A-Z]{3,6}\)', '', stripped_btitle)
        stripped_btitle = stripped_btitle\
            .replace('Proceedings of the', '')\
            .replace('Proceedings', '')
        entry.update(booktitle=stripped_btitle)

    if 'journal' in entry:
        entry.update(
            journal=utils.title_if_mostly_upper_case(entry['journal']))

    if 'pages' in entry:
        entry.update(pages=utils.unify_pages_field(entry['pages']))
        if not re.match(r'^\d*$', entry['pages']) and \
                not re.match(r'^\d*--\d*$', entry['pages']) and\
                not re.match(r'^[xivXIV]*--[xivXIV]*$', entry['pages']):
            logging.info(f' {entry["ID"]}:'.ljust(18, ' ') +
                         f'Unusual pages: {entry["pages"]}')

    if 'doi' in entry:
        entry.update(doi=entry['doi'].replace('http://dx.doi.org/', ''))

    if 'issue' in entry and 'number' not in entry:
        entry.update(issue=entry['number'])
        del entry['number']

    return entry


LOCAL_JOURNAL_ABBREVIATIONS, \
    LOCAL_JOURNAL_VARIATIONS, \
    LOCAL_CONFERENCE_ABBREVIATIONS = \
    utils.retrieve_local_resources()


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
    utils.retrieve_crowd_resources()


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


def crossref_query(entry):
    # https://github.com/CrossRef/rest-api-doc
    api_url = 'https://api.crossref.org/works?'
    bibliographic = entry['title'] + ' ' + entry.get('year', '')
    bibliographic = bibliographic.replace('...', '').replace('…', '')
    container_title = utils.get_container_title(entry)
    container_title = container_title.replace('...', '').replace('…', '')
    author_string = entry['author'].replace('...', '').replace('…', '')
    params = {'rows': '5', 'query.bibliographic': bibliographic,
              'query.author': author_string,
              'query.container-title': container_title}
    url = api_url + urllib.parse.urlencode(params)
    headers = {'user-agent':
               f'prepare.py (mailto:{repo_setup.config["EMAIL"]})'}
    ret = requests.get(url, headers=headers)
    if ret.status_code != 200:
        return

    data = json.loads(ret.text)
    items = data['message']['items']
    most_similar = {
        'crossref_title': '',
        'similarity': 0,
        'doi': '',
    }
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
            similarities = [title_similarity, container_similarity]

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

    time.sleep(1)
    return {'success': True, 'result': most_similar}


def get_doi_from_crossref(entry):
    if ('title' not in entry) or ('doi' in entry):
        return entry

    MAX_RETRIES_ON_ERROR = 3
    # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
    if len(entry['title']) > 35 and 'doi' not in entry:
        try:
            ret = crossref_query(entry)
            retries = 0
            while not ret['success'] and retries < MAX_RETRIES_ON_ERROR:
                retries += 1
                ret = crossref_query(entry)

            # print(ret)
            # print('\n\n\n')
            # dummy = entry.copy()
            # dummy['doi'] = ret['result']['doi']
            # dummy = retrieve_doi_metadata(dummy)
            # print(dummy)
            # print(dedupe.get_entry_similarity(dummy, entry.copy()))
            # if dedupe.get_entry_similarity(dummy, entry.copy()) > 0.95:

            if ret['result']['similarity'] > 0.9:
                entry.update(doi=ret['result']['doi'])
        except KeyboardInterrupt:
            sys.exit()
    return entry


def get_metadata_from_semantic_scholar(entry):
    if 'doi' in entry:
        return entry

    search_api_url = \
        'https://api.semanticscholar.org/graph/v1/paper/search?query='
    url = search_api_url + entry.get('title', '').replace(' ', '+')
    headers = {'user-agent':
               f'prepare.py (mailto:{repo_setup.config["EMAIL"]})'}
    ret = requests.get(url, headers=headers)

    try:
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
        retrieved_entry = {}

        if 'authors' in item:
            authors_string = ' and '.join([author['name']
                                           for author in item['authors']])
            retrieved_entry.update(
                author=utils.format_author_field(authors_string))
        if 'abstract' in item:
            retrieved_entry.update(abstract=item['abstract'])
        if 'doi' in item:
            retrieved_entry.update(doi=item['doi'])
        if 'title' in item:
            retrieved_entry.update(title=item['title'])
        if 'year' in item:
            retrieved_entry.update(year=item['year'])
        if 'venue' in item:
            retrieved_entry.update(venue=item['venue'])
        if 'url' in item:
            retrieved_entry.update(semantic_scholar_id=item['url'])

        keys_to_drop = []
        for key, value in retrieved_entry.items():
            retrieved_entry[key] = str(value).replace(
                '\n', ' ').lstrip().rstrip()
            if value in ['', 'None'] or value is None:
                keys_to_drop.append(key)
        for key in keys_to_drop:
            del retrieved_entry[key]

        red_entry_copy = entry.copy()
        for key in ['volume', 'number', 'issue', 'pages']:
            if key in red_entry_copy:
                del red_entry_copy[key]

        # sim = dedupe.get_entry_similarity(red_entry_copy,
        #                 retrieved_entry.copy())
        # if sim > 0.7:
        #     print(entry)
        #     print(retrieved_entry)
        #     print(sim)
        #     print('\n\n\n\n')

        if dedupe.get_entry_similarity(red_entry_copy,
                                       retrieved_entry.copy()) > 0.9:
            if 'title' in retrieved_entry:
                entry.update(title=retrieved_entry['title'])
            if 'doi' in retrieved_entry:
                entry.update(doi=retrieved_entry['doi'])
            if 'abstract' in retrieved_entry:
                entry.update(abstract=retrieved_entry['abstract'])
            if 'author' in retrieved_entry:
                entry.update(author=retrieved_entry['author'])
            if 'year' in retrieved_entry:
                entry.update(year=retrieved_entry['year'])
            if 'abstract' in retrieved_entry:
                entry.update(abstract=retrieved_entry['abstract'])
            if 'venue' in retrieved_entry:
                if 'journal' in entry:
                    entry.update(journal=retrieved_entry['venue'])
                if 'booktitle' in entry:
                    entry.update(booktitle=retrieved_entry['venue'])
            entry.update(
                semantic_scholar_id=retrieved_entry['semantic_scholar_id'])

    except KeyError:
        pass

    except UnicodeEncodeError:
        logging.error(
            'UnicodeEncodeError - this needs to be fixed at some time')
        pass

    return entry


def get_dblp_venue(venue_string):
    venue = venue_string
    api_url = 'https://dblp.org/search/venue/api?q='
    url = api_url + venue_string.replace(' ', '+') + '&format=json'
    headers = {'user-agent':
               f'prepare.py (mailto:{repo_setup.config["EMAIL"]})'}
    ret = requests.get(url, headers=headers)

    data = json.loads(ret.text)
    venue = data['result']['hits']['hit'][0]['info']['venue']
    re.sub(r' \(.*?\)', '', venue)

    return venue


def get_metadata_from_dblp(entry):
    if 'doi' in entry:
        return entry

    api_url = 'https://dblp.org/search/publ/api?q='
    url = api_url + entry.get('title', '').replace(' ', '+') + '&format=json'
    # print(url)
    headers = {'user-agent':
               f'prepare.py (mailto:{repo_setup.config["EMAIL"]})'}
    ret = requests.get(url, headers=headers)

    try:

        data = json.loads(ret.text)
        items = data['result']['hits']['hit']
        item = items[0]['info']

        author_string = ' and '.join([author['text']
                                     for author in item['authors']['author']])
        author_string = utils.format_author_field(author_string)

        author_similarity = ratio(
            dedupe.format_authors_string(author_string),
            dedupe.format_authors_string(entry['author']),
        )
        title_similarity = ratio(
            item['title'].lower(),
            entry['title'].lower(),
        )
        # container_similarity = ratio(
        #     item['venue'].lower(),
        #     utils.get_container_title(entry).lower(),
        # )
        year_similarity = ratio(
            item['year'],
            entry['year'],
        )
        # print(f'author_similarity: {author_similarity}')
        # print(f'title_similarity: {title_similarity}')
        # print(f'container_similarity: {container_similarity}')
        # print(f'year_similarity: {year_similarity}')

        weights = [0.4, 0.3, 0.3]
        similarities = [title_similarity, author_similarity, year_similarity]

        similarity = sum(similarities[g] * weights[g]
                         for g in range(len(similarities)))
        # print(similarity)
        if similarity > 0.99:
            if 'Journal Articles' == item['type']:
                if 'booktitle' in entry:
                    del entry['booktitle']
                entry['ENTRYTYPE'] = 'article'
                entry['journal'] = get_dblp_venue(item['venue'])
                entry['volume'] = item['volume']
                entry['issue'] = item['number']
            if 'Conference and Workshop Papers' == item['type']:
                if 'journal' in entry:
                    del entry['journal']
                entry['ENTRYTYPE'] = 'inproceedings'
                entry['booktitle'] = get_dblp_venue(item['venue'])
            if 'doi' in item:
                entry['doi'] = item['doi']
            entry['dblp_key'] = 'https://dblp.org/rec/' + item['key']
    except KeyError:
        pass
    except UnicodeEncodeError:
        logging.error(
            'UnicodeEncodeError - this needs to be fixed at some time')
        pass

    return entry


# https://www.crossref.org/blog/dois-and-matching-regular-expressions/
doi_regex = re.compile(r'10\.\d{4,9}/[-._;/:A-Za-z0-9]*')


def get_doi_from_links(entry):
    if 'doi' in entry:
        return entry

    url = ''
    url = entry.get('url', entry.get('fulltext', ''))
    if url != '':
        try:
            r = requests.get(url)
            res = re.findall(doi_regex, r.text)
            if res:
                if len(res) == 1:
                    ret_doi = res[0]
                    entry['doi'] = ret_doi
                else:
                    counter = collections.Counter(res)
                    ret_doi = counter.most_common(1)[0][0]
                    entry['doi'] = ret_doi

                # print('  - TODO: retrieve meta-data and valdiate, '
                #       'especially if multiple dois matched')
                doi_entry = {'doi': entry['doi'], 'ID': entry['ID']}
                doi_entry = retrieve_doi_metadata(doi_entry)
                if dedupe.get_entry_similarity(entry.copy(), doi_entry) < 0.95:
                    if 'doi' in entry:
                        del entry['doi']

                if 'doi' in entry:
                    logging.info(f'Added doi from website: {entry["doi"]}')

        except requests.exceptions.ConnectionError:
            return entry
            pass
        except Exception as e:
            print(f'exception: {e}')
            return entry
            pass
    return entry


def retrieve_doi_metadata(entry):
    # for testing:
    # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
    # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

    if 'doi' not in entry:
        return entry

    # For exceptions:
    orig_entry = entry.copy()

    try:
        url = 'http://dx.doi.org/' + entry['doi']
        headers = {'accept': 'application/vnd.citationstyles.csl+json'}
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                         f'metadata for doi {entry["doi"]} '
                         'not (yet) available')
            return entry

        full_data = r.text
        retrieved_record = json.loads(full_data)
        if 'type' in retrieved_record:
            if 'journal-article' == retrieved_record.get('type', 'NA'):
                entry['ENTRYTYPE'] = 'article'
            if 'proceedings-article' == retrieved_record.get('type', 'NA'):
                entry['ENTRYTYPE'] = 'inproceedings'
            if 'book' == retrieved_record.get('type', 'NA'):
                entry['ENTRYTYPE'] = 'book'
        author_string = ''
        for author in retrieved_record.get('author', ''):
            if 'family' not in author:
                continue
            if '' != author_string:
                author_string = author_string + ' and '
            author_given = author.get('given', '')
            # Use local given name when no given name is provided by doi
            if '' == author_given:
                authors = entry['author'].split(' and ')
                local_author_string = [x for x in authors
                                       if author.get('family', '').lower()
                                       in x.lower()]
                local_author = HumanName(local_author_string.pop())

                author_string = author_string + \
                    author.get('family', '') + ', ' + \
                    local_author.first + ' ' + local_author.middle
                # Note: if there is an exception, use:
                # author_string = author_string + \
                # author.get('family', '')
            else:
                author_string = author_string + \
                    author.get('family', '') + ', ' + \
                    author.get('given', '')

        if not author_string == '':
            if utils.mostly_upper_case(author_string
                                       .replace(' and ', '')
                                       .replace('Jr', '')):

                names = author_string.split(' and ')
                entry.update(author='')
                for name in names:
                    # Note: https://github.com/derek73/python-nameparser
                    # is very effective (maybe not perfect)
                    parsed_name = HumanName(name)
                    parsed_name.string_format = \
                        '{last} {suffix}, {first} ({nickname}) {middle}'
                    parsed_name.capitalize(force=True)
                    entry.update(author=entry['author'] + ' and ' +
                                 str(parsed_name).replace(' , ', ', '))
                if entry['author'].startswith(' and '):
                    entry.update(author=entry['author'][5:]
                                 .rstrip()
                                 .replace('  ', ' '))
            else:
                entry.update(author=str(
                    author_string).rstrip().replace('  ', ' '))

        retrieved_title = retrieved_record.get('title', '')
        if not retrieved_title == '':
            entry.update(title=re.sub(r'\s+', ' ', str(retrieved_title))
                         .replace('\n', ' '))
        try:
            if 'published-print' in retrieved_record:
                date_parts = \
                    retrieved_record['published-print']['date-parts']
                entry.update(year=str(date_parts[0][0]))
            elif 'published-online' in retrieved_record:
                date_parts = \
                    retrieved_record['published-online']['date-parts']
                entry.update(year=str(date_parts[0][0]))
        except KeyError:
            pass

        retrieved_pages = retrieved_record.get('page', '')
        if retrieved_pages != '':
            # DOI data often has only the first page.
            if not entry.get('pages', 'no_pages') in retrieved_pages \
                    and '-' in retrieved_pages:
                entry.update(pages=utils.unify_pages_field(
                    str(retrieved_pages)))
        retrieved_volume = retrieved_record.get('volume', '')
        if not retrieved_volume == '':
            entry.update(volume=str(retrieved_volume))

        retrieved_issue = retrieved_record.get('issue', '')
        if 'journal-issue' in retrieved_record:
            if 'issue' in retrieved_record['journal-issue']:
                retrieved_issue = retrieved_record['journal-issue']['issue']
        if not retrieved_issue == '':
            entry.update(issue=str(retrieved_issue))

        retrieved_container_title = \
            str(retrieved_record.get('container-title', ''))
        if not retrieved_container_title == '':
            if 'journal' in entry:
                entry.update(journal=retrieved_container_title)
            elif 'booktitle' in entry:
                entry.update(booktitle=retrieved_container_title)
            elif 'series' in entry:
                entry.update(series=retrieved_container_title)

            # if 'series' in entry:
            #     if entry['series'] != retrieved_container_title:
            #             entry.update(series=retrieved_container_title)

        if 'abstract' not in entry:
            retrieved_abstract = retrieved_record.get('abstract', '')
            if not retrieved_abstract == '':

                retrieved_abstract = \
                    re.sub(
                        r'<\/?jats\:[^>]*>',
                        ' ',
                        retrieved_abstract,
                    )
                retrieved_abstract = \
                    re.sub(r'\s+', ' ', retrieved_abstract)
                entry.update(abstract=str(retrieved_abstract).replace('\n', '')
                             .lstrip().rstrip())
    # except IndexError:
    #     logging.error(f'Index error (authors?) for {entry["ID"]}')
    #     return orig_entry
    #     pass
    # except json.decoder.JSONDecodeError:
    #     logging.error(f'{entry.get("ID", "NO_ID")}'.ljust(17, ' ') +
    #                   f'DOI retrieval error ({entry["doi"]})')
    #     return orig_entry
    #     pass
    # except TypeError:
    #     logging.error(f'Type error: {entry["ID"]}')
    #     return orig_entry
    #     pass
    except requests.exceptions.ConnectionError:
        logging.error(f'ConnectionError: {entry["ID"]}')
        return orig_entry
        pass

    entry['complete_based_on_doi'] = 'True'

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
    # else:
    #     logging.info(f'No field requirements set for {entry["ENTRYTYPE"]}')

    return sufficiently_complete


def is_doi_complete(entry):
    # Note: complete_based_on_doi is set at the end of retrieve_doi_metadata
    return 'True' == entry.get('complete_based_on_doi', 'NA')


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
    # else:
    #  logging.info(f'No field inconsistencies set for {entry["ENTRYTYPE"]}')

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
    'status', 'fulltext', 'entry_link',
    'dblp_key', 'semantic_scholar_id'
]
fields_to_drop = [
    'type', 'url', 'organization',
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
    'related', 'bibsource', 'timestamp', 'biburl',
    'complete_based_on_doi'
]


def drop_fields(entry):
    for key in list(entry):
        if 'NA' == entry[key]:
            del entry[key]
        if(key not in fields_to_keep):
            # drop all fields not in fields_to_keep
            entry.pop(key)
            # warn if fields are dropped that are not in fields_to_drop
            if key not in fields_to_drop:
                logging.info(f'Dropped {key} field')
    return entry


def log_notifications(entry, unprepared_entry):

    change = 1 - dedupe.get_entry_similarity(entry.copy(), unprepared_entry)
    if change > 0.1:
        logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                     f'Change score: {round(change, 2)}')

    if not (is_complete(entry) or is_doi_complete(entry)):
        logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                     f'{str(entry["ENTRYTYPE"]).title()} '
                     f'missing {missing_fields(entry)}')
    if has_inconsistent_fields(entry):
        logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                     f'{str(entry["ENTRYTYPE"]).title()} '
                     f'with {get_inconsistencies(entry)} field(s)'
                     ' (inconsistent')
    if has_incomplete_fields(entry):
        logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                     f'Incomplete fields {get_incomplete_fields(entry)}')
    return


def prepare(entry):
    global current_batch_counter

    if 'imported' != entry['status']:
        return entry

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return entry
        else:
            current_batch_counter.value += 1

    unprepared_entry = entry.copy()

    entry = correct_entrytype(entry)

    entry = homogenize_entry(entry)

    entry = apply_local_rules(entry)

    entry = apply_crowd_rules(entry)

    # Note: we require (almost) perfect matches for the following.
    # Cases with higher dissimilarity will be handled in the man_prep.py
    entry = get_doi_from_crossref(entry)

    entry = get_metadata_from_dblp(entry)

    entry = get_metadata_from_semantic_scholar(entry)

    entry = get_doi_from_links(entry)

    entry = retrieve_doi_metadata(entry)

    if (is_complete(entry) or is_doi_complete(entry)) and \
            not has_inconsistent_fields(entry) and \
            not has_incomplete_fields(entry):
        entry = drop_fields(entry)
        # logging.info(f'Successfully prepared {entry["ID"]}')
        entry.update(status='prepared')
    else:
        if 'complete_based_on_doi' in entry:
            del entry['complete_based_on_doi']
        log_notifications(entry, unprepared_entry)
        entry.update(status='needs_manual_preparation')

    return entry


def create_commit(repo, bib_database):
    global prepared
    global need_manual_prep

    MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    if MAIN_REFERENCES in [item.a_path for item in repo.index.diff(None)] or \
            MAIN_REFERENCES in repo.untracked_files:

        repo.index.add([MAIN_REFERENCES])

        processing_report = ''
        if os.path.exists('report.log'):
            with open('report.log') as f:
                processing_report = f.readlines()
            processing_report = \
                f'\nProcessing (batch size: {BATCH_SIZE})\n' + \
                ''.join(processing_report)

        repo.index.commit(
            '⚙️ Prepare ' + MAIN_REFERENCES + utils.get_version_flag() +
            utils.get_commit_report(os.path.basename(__file__)) +
            processing_report,
            author=git.Actor('script:prepare.py', ''),
            committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                                repo_setup.config['EMAIL']),
        )
        logging.info('Created commit')
        print()
        with open('report.log', 'r+') as f:
            f.truncate(0)
        return True
    else:
        return False


def prepare_entries(db, repo):
    global prepared
    global need_manual_prep

    process.check_delay(db, min_status_requirement='imported')
    with open('report.log', 'r+') as f:
        f.truncate(0)

    logging.info('Prepare')

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logging.info('Continuing batch preparation started earlier')

        prepared = len([x for x in db.entries
                        if 'prepared' == x.get('status', 'NA')])
        need_manual_prep = \
            len([x for x in db.entries
                if 'needs_manual_preparation' == x.get('status', 'NA')])

        pool = mp.Pool(repo_setup.config['CPUS'])
        db.entries = pool.map(prepare, db.entries)
        pool.close()
        pool.join()

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        if batch_end > 0:
            logging.info('Completed preparation batch '
                         f'(entries {batch_start} to {batch_end})')

            prepared = len([x for x in db.entries
                            if 'prepared' == x.get('status', 'NA')]) - prepared
            need_manual_prep = \
                len([x for x in db.entries
                    if 'needs_manual_preparation' == x.get('status', 'NA')]) \
                - need_manual_prep

            if prepared > 0:
                logging.info(f'Summary: Prepared {prepared} entries')
            if need_manual_prep > 0:
                logging.info(f'Summary: Marked {need_manual_prep} entries ' +
                             'for manual preparation')

            in_process = create_commit(repo, db)

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logging.info('No additional entries to prepare')
            break

    print()

    return db
