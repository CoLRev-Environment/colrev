#! /usr/bin/env python
import collections
import configparser
import json
import logging
import re
import sys
import time
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

import bibtexparser
import git
import requests
from Levenshtein import ratio
from nameparser import HumanName

from review_template import entry_hash_function
from review_template import utils

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']


logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']

EMPTY_RESULT = {
    'crossref_title': '',
    'similarity': 0,
    'doi': '',
}
MAX_RETRIES_ON_ERROR = 3

LOCAL_JOURNAL_ABBREVIATIONS, \
    LOCAL_JOURNAL_VARIATIONS, \
    LOCAL_CONFERENCE_ABBREVIATIONS = \
    utils.retrieve_local_resources()

CR_JOURNAL_ABBREVIATIONS, \
    CR_JOURNAL_VARIATIONS, \
    CR_CONFERENCE_ABBREVIATIONS = \
    utils.retrieve_crowd_resources()


def crossref_query(entry):
    # https://github.com/CrossRef/rest-api-doc
    api_url = 'https://api.crossref.org/works?'
    params = {'rows': '5', 'query.bibliographic': entry['title']}
    url = api_url + urlencode(params, quote_via=quote_plus)
    request = Request(url)
    request.add_header(
        'User-Agent', 'RecordPreparer (mailto:' +
        config['general']['EMAIL'] + ')',
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


def homogenize_entry(entry):

    fields_to_process = [
        'author', 'year', 'title',
        'journal', 'booktitle', 'series',
        'volume', 'number', 'pages', 'doi',
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

    if 'journal' in entry:
        entry.update(
            journal=utils.title_if_mostly_upper_case(entry['journal']))

    if 'pages' in entry:
        entry.update(pages=utils.unify_pages_field(entry['pages']))

    if 'doi' in entry:
        entry.update(doi=entry['doi'].replace('http://dx.doi.org/', ''))

    if 'issue' in entry and 'number' not in entry:
        entry.update(number=entry['issue'])
        del entry['issue']

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
        except requests.exceptions.ConnectionError:
            return entry
            pass
        res = re.findall(doi_regex, r.text)
        if res:
            if len(res) == 1:
                ret_doi = res[0]
                entry['doi'] = ret_doi
            else:
                counter = collections.Counter(res)
                ret_doi = counter.most_common(1)[0][0]
                entry['doi'] = ret_doi
            print('  - TODO: if multiple dois matche d, '
                  'retrieve meta-data and valdiate')
            print('  - Added doi from website: ' + entry['doi'])

    return entry


def get_doi_from_crossref(entry):
    if 'title' not in entry:
        return entry
    # https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
    if len(entry['title']) > 60 and 'doi' not in entry:
        try:
            ret = crossref_query(entry)
            retries = 0
            while not ret['success'] and retries < MAX_RETRIES_ON_ERROR:
                retries += 1
                ret = crossref_query(entry)
            if ret['result']['similarity'] > 0.95:
                entry.update(doi=ret['result']['doi'])
        except KeyboardInterrupt:
            sys.exit()
    return entry


def retrieve_doi_metadata(entry):
    # for testing:
    # curl -iL -H "accept: application/vnd.citationstyles.csl+json"
    # -H "Content-Type: application/json" http://dx.doi.org/10.1111/joop.12368

    if 'doi' not in entry:
        return entry

    try:
        full_data = doi2json(entry['doi'])
        retrieved_record = json.loads(full_data)
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
        if not retrieved_issue == '':
            entry.update(number=str(retrieved_issue))

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
    except IndexError:
        print(f'  - WARNING: Index error (authors?) for {entry["ID"]}')
        entry.update(status='imported')
        pass
    except json.decoder.JSONDecodeError:
        print(f'  - WARNING: Doi retrieval error: {entry["ID"]} / '
              f'{entry["doi"]}')
        entry.update(status='imported')
        pass
    except TypeError:
        print(f'  - WARNING: Type error: : {entry["ID"]}')
        entry.update(status='imported')
        pass
    except requests.exceptions.ConnectionError:
        print(f'  - WARNING: ConnectionError: : {entry["ID"]}')
        entry.update(status='imported')
        pass

    return entry


def regenerate_citation_key(entry, bib_database):

    if 'imported' != entry['status']:

        # Recreate citation_keys
        # (mainly if it differs, i.e., if there are changes in authors/years)
        try:
            entry.update(ID=utils.generate_citation_key(
                entry, bib_database, entry_in_bib_db=True))
        except utils.CitationKeyPropagationError:
            # print('WARNING: preparing entry with propagated citation_key:',
            #   entry['ID'])
            pass

    return entry


def correct_entrytypes(entry):

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


def speculative_changes(entry):

    entry = correct_entrytypes(entry)

    # Moved journal processing to importer
    # TODO: reinclude (as a function?)

    if 'booktitle' in entry:

        stripped_btitle = re.sub(r'\d{4}', '', entry['booktitle'])
        stripped_btitle = re.sub(r'\d{1,2}th', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}nd', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}rd', '', stripped_btitle)
        stripped_btitle = re.sub(r'\d{1,2}st', '', stripped_btitle)
        stripped_btitle = re.sub(r'\([A-Z]{3,6}\)', '', stripped_btitle)
        stripped_btitle = stripped_btitle\
            .replace('Proceedings of the', '')\
            .replace('Proceedings', '')

    return entry


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


def prepare(entry):

    if 'imported' != entry['status']:
        return entry

    entry.update(status='prepared')

    entry = homogenize_entry(entry)

    entry = apply_local_rules(entry)

    entry = apply_crowd_rules(entry)

    entry = speculative_changes(entry)

    if 'doi' not in entry:
        entry = get_doi_from_crossref(entry)
    if 'doi' not in entry:
        entry = get_doi_from_links(entry)

    entry = retrieve_doi_metadata(entry)

    # Note: tbd. whether we regenerate the citation_key here...
    # we have to make sure that there are no conflicts.
    # entry = regenerate_citation_key(entry)

    if 'doi' in entry and 'title' in entry and \
            'journal' in entry and 'year' in entry:
        # in this case, it would be ok to have no author
        entry.update(status='prepared')
    # TODO: the following if-statement is redundant (check!) because these
    # missing fields should be provided before hash-ids are created!
    if 'title' not in entry or \
        'author' not in entry or \
            'year' not in entry or \
            not any(x in entry for x in
                    ['journal', 'booktitle', 'school', 'book', 'series']):
        entry.update(status='needs_manual_preparation')
    if 'title' in entry and 'author' in entry and 'year' in entry and \
            'book' == entry.get('ENTRYTYPE', ''):
        entry.update(status='prepared')

    if entry.get('title', '').endswith('...') or \
            entry.get('title', '').endswith('…') or \
            entry.get('journal', '').endswith('...') or \
            entry.get('journal', '').endswith('…') or \
            entry.get('booktitle', '').endswith('...') or \
            entry.get('booktitle', '').endswith('…') or \
            entry.get('author', '').endswith('...') or \
            entry.get('author', '').endswith('…'):
        entry.update(status='needs_manual_preparation')

    return entry


def create_commit(r, bib_database):

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)] or \
            MAIN_REFERENCES in r.untracked_files:

        # to avoid failing pre-commit hooks
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        utils.save_bib_file(bib_database, MAIN_REFERENCES)

        r.index.add([MAIN_REFERENCES])

        flag, flag_details = utils.get_version_flags()

        r.index.commit(
            '⚙️ Prepare ' + MAIN_REFERENCES + flag + flag_details +
            '\n - ' + utils.get_package_details(),
            author=git.Actor('script:prepare.py', ''),
            committer=git.Actor(config['general']['GIT_ACTOR'],
                                config['general']['EMAIL']),
        )

        # print('Created commit: Prepare ' + MAIN_REFERENCES)
        return True
    else:
        print('- No additional prepared entries available')
        return False


def test_prepare():
    bibtex_str = """@article{Andersen2019,
                    author    = {Andersen, Jonas},
                    journal   = {Journal of Information Systems},
                    title     = {Self-Organizing in Blockchain},
                    year      = {2019},
                    pages     = {1242--1273},
                    doi       = {10.17705/1jais.00566},
                    }"""

    bib_database = bibtexparser.loads(bibtex_str)
    entry = bib_database.entries[0]
    print(prepare(entry))

    return


if __name__ == '__main__':
    test_prepare()
    # https://github.com/nschloe/betterbib
