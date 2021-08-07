#! /usr/bin/env python
import csv
import os
import re

import bibtexparser
import entry_hash_function
import git
import pandas as pd
import utils
import yaml
from fuzzywuzzy import fuzz

nr_entries_added = 0
nr_current_entries = 0

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

with open('private_config.yaml') as private_config_yaml:
    private_config = yaml.load(private_config_yaml, Loader=yaml.FullLoader)

DEBUG_MODE = (1 == private_config['params']['DEBUG_MODE'])

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']

pd.options.mode.chained_assignment = None  # default='warn'


def format_authors_string(authors):
    authors = str(authors).lower()
    authors_string = ''
    authors = utils.remove_accents(authors)

    # abbreviate first names
    # "Webster, Jane" -> "Webster, J"
    # also remove all special characters and do not include separators (and)
    for author in authors.split(' and '):
        if ',' in author:
            last_names = [word[0] for word in author.split(
                ',')[1].split(' ') if len(word) > 0]
            authors_string = authors_string + \
                author.split(',')[0] + ' ' + ' '.join(last_names) + ' '
        else:
            authors_string = authors_string + author + ' '
    authors_string = re.sub(r'[^A-Za-z0-9, ]+', '', authors_string.rstrip())
    return authors_string


def get_entry_similarity(entry_a, entry_b):
    if 'author' not in entry_a:
        entry_a['author'] = ''
    if 'year' not in entry_a:
        entry_a['year'] = ''
    if 'journal' in entry_a:
        if 'volume' not in entry_a:
            entry_a['volume'] = ''
        if 'number' not in entry_a:
            entry_a['number'] = ''
        if 'pages' not in entry_a:
            entry_a['pages'] = ''
    else:
        if 'booktitle' not in entry_a:
            entry_a['booktitle'] = ''
    if 'author' not in entry_b:
        entry_b['author'] = ''
    if 'year' not in entry_b:
        entry_b['year'] = ''
    if 'journal' in entry_b:
        if 'volume' not in entry_b:
            entry_b['volume'] = ''
        if 'number' not in entry_b:
            entry_b['number'] = ''
        if 'pages' not in entry_b:
            entry_b['pages'] = ''
    else:
        if 'booktitle' not in entry_b:
            entry_b['booktitle'] = ''

    df_a = pd.DataFrame.from_dict([entry_a])
    df_b = pd.DataFrame.from_dict([entry_b])

    return get_similarity(df_a.iloc[0], df_b.iloc[0])


def get_similarity(df_a, df_b):

    author_similarity = fuzz.partial_ratio(df_a['author'], df_b['author'])/100

    title_similarity = fuzz.ratio(df_a['title'], df_b['title'])/100

    # partial ratio (catching 2010-10 or 2001-2002)
    year_similarity = fuzz.partial_ratio(df_a['year'], df_b['year'])/100

    outlet_similarity = \
        fuzz.ratio(df_a['container_title'], df_b['container_title'])/100

    if (str(df_a['journal']) != 'nan'):
        # Note: for journals papers, we expect more details
        if df_a['volume'] == df_b['volume']:
            volume_similarity = 1
        else:
            volume_similarity = 0
        if df_a['number'] == df_b['number']:
            number_similarity = 1
        else:
            number_similarity = 0
        # sometimes, only the first page is provided.
        if str(df_a['pages']) == 'nan' or str(df_b['pages']) == 'nan':
            pages_similarity = 1
        else:
            if df_a['pages'] == df_b['pages']:
                pages_similarity = 1
            else:
                if df_a['pages'].split('-')[0] == df_b['pages'].split('-')[0]:
                    pages_similarity = 1
                else:
                    pages_similarity = 0

        # Put more weithe on other fields if the title is very common
        # ie., non-distinctive
        # The list is based on a large export of distinct papers, tabulated
        # according to titles and sorted by frequency
        if [df_a['title'], df_b['title']] in \
            [['editorial', 'editorial'],
             ['editorial introduction', 'editorial introduction'],
             ['editorial notes', 'editorial notes'],
             ["editor's comments", "editor's comments"],
             ['book reviews', 'book reviews'],
             ['editorial note', 'editorial note'],
             ]:
            weights = [0.175, 0, 0.175, 0.175, 0.175, 0.175, 0.125]
        else:
            weights = [0.25, 0.3, 0.13, 0.2, 0.05, 0.05, 0.02]

        similarities = [author_similarity,
                        title_similarity,
                        year_similarity,
                        outlet_similarity,
                        volume_similarity,
                        number_similarity,
                        pages_similarity]

    else:

        weights = [0.15, 0.75, 0.05, 0.05]
        similarities = [author_similarity,
                        title_similarity,
                        year_similarity,
                        outlet_similarity]

    weighted_average = sum(similarities[g] * weights[g]
                           for g in range(len(similarities)))

    return round(weighted_average, 4)


def prep_references(references):
    if 'volume' not in references:
        references['volume'] = 'nan'
    if 'number' not in references:
        references['number'] = 'nan'
    if 'pages' not in references:
        references['pages'] = 'nan'
    if 'year' not in references:
        references['year'] = 'nan'
    else:
        references['year'] = references['year'].astype(str)
    if 'author' not in references:
        references['author'] = 'nan'
    else:
        references['author'] = references['author']\
            .apply(lambda x: format_authors_string(x))
    if 'title' not in references:
        references['title'] = 'nan'
    else:
        references['title'] = references['title']\
            .str.replace(r'[^A-Za-z0-9, ]+', '', regex=True)\
            .str.lower()
    if 'journal' not in references:
        references['journal'] = ''
    else:
        references['journal'] = references['journal']\
            .str.replace(r'[^A-Za-z0-9, ]+', '', regex=True)\
            .str.lower()
    if 'booktitle' not in references:
        references['booktitle'] = ''
    else:
        references['booktitle'] = references['booktitle']\
            .str.replace(r'[^A-Za-z0-9, ]+', '', regex=True)\
            .str.lower()
    if 'series' not in references:
        references['series'] = ''
    else:
        references['series'] = references['series']\
            .str.replace(r'[^A-Za-z0-9, ]+', '', regex=True)\
            .str.lower()

    references['container_title'] = references['journal'].fillna('') + \
        references['booktitle'].fillna('') + \
        references['series'].fillna('')

    references.drop(references.columns.difference(['ID',
                                                   'author',
                                                   'title',
                                                   'year',
                                                   'journal',
                                                   'container_title',
                                                   'volume',
                                                   'number',
                                                   'pages']), 1, inplace=True)

    return references


def calculate_similarities_entry(references):
    # Note: per definition, similarities are needed relative to the first row.
    references = prep_references(references)
    # references.to_csv('preped_references.csv')
    references['similarity'] = 0
    sim_col = references.columns.get_loc('similarity')
    for base_entry_i in range(1, references.shape[0]):
        references.iloc[base_entry_i, sim_col] = \
            get_similarity(references.iloc[base_entry_i],
                           references.iloc[0])
    # Note: return all other entries (not the comparison entry/first row)
    # and restrict it to the ID and similarity
    ck_col = references.columns.get_loc('ID')
    sim_col = references.columns.get_loc('similarity')
    return references.iloc[1:, [ck_col, sim_col]]


def get_combined_hash_id_list(references, ref_id_tuple):

    hash_ids_entry_1 = \
        references.loc[references['ID'] ==
                       ref_id_tuple[0]]['hash_id'].values[0]
    hash_ids_entry_2 = \
        references.loc[references['ID'] ==
                       ref_id_tuple[1]]['hash_id'].values[0]
    if not isinstance(hash_ids_entry_1, str):
        hash_ids_entry_1 = []
    else:
        hash_ids_entry_1 = hash_ids_entry_1.split(',')
    if not isinstance(hash_ids_entry_2, str):
        hash_ids_entry_2 = []
    else:
        hash_ids_entry_2 = hash_ids_entry_2.split(',')

    combined_hash_list = set(hash_ids_entry_1
                             + hash_ids_entry_2)

    return ','.join(combined_hash_list)


def create_commit(r, bib_database):

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    merge_details = ''
    if os.path.exists('duplicate_tuples.csv'):
        with open('duplicate_tuples.csv') as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                if row[0] != 'ID1':
                    merge_details += row[0] + ' < ' + row[1] + '\n'
        os.remove('duplicate_tuples.csv')

    if merge_details != '':
        merge_details = '\n\nDuplicates removed:\n' + merge_details

    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)] or \
            MAIN_REFERENCES in r.untracked_files:

        # to avoid failing pre-commit hooks
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        utils.save_bib_file(bib_database, MAIN_REFERENCES)

        if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)]:
            r.index.add([MAIN_REFERENCES])
            if os.path.exists('potential_duplicate_tuples.csv'):
                r.index.add(['potential_duplicate_tuples.csv'])
            r.index.commit(
                '⚙️ Merge duplicates' + merge_details,
                author=git.Actor('script:merge_duplicates.py', ''),
            )
    return


def test_merge():

    bibtex_str = """@article{Appan2012,
                    author    = {Appan, and Browne,},
                    journal   = {MIS Quarterly},
                    title     = {The Impact of Analyst-Induced Misinformation},
                    year      = {2012},
                    number    = {1},
                    pages     = {85},
                    volume    = {36},
                    doi       = {10.2307/41410407},
                    hash_id   = {300a3700f5440cb37f39b05c866dc0a33cefb78de93c},
                    }

                    @article{Appan2012a,
                    author    = {Appan, Radha and Browne, Glenn J.},
                    journal   = {MIS Quarterly},
                    title     = {The Impact of Analyst-Induced Misinformation},
                    year      = {2012},
                    number    = {1},
                    pages     = {22},
                    volume    = {36},
                    doi       = {10.2307/41410407},
                    hash_id   = {427967442a90d7f27187e66fd5b66fa94ab2d5da1bf9},
                    }"""

    bib_database = bibtexparser.loads(bibtex_str)
    entry_a = bib_database.entries[0]
    entry_b = bib_database.entries[1]
    df_a = pd.DataFrame.from_dict([entry_a])
    df_b = pd.DataFrame.from_dict([entry_b])

    print(get_similarity(df_a.iloc[0], df_b.iloc[0]))

    return


if __name__ == '__main__':
    test_merge()
    input('continue')

    print('')
    print('')

    # print('Remove the following restriction:')
    # bib_database.entries = bib_database.entries[:100]


#
#    references, tuples_to_process = \
#        interactively_merge_entries(references,
#                                    tuples_to_process)
#
#    store_changes(references, bib_database)
#
#    # create a commit if there are changes (removed duplicates)
#    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)]:
#        r.index.add([MAIN_REFERENCES])
#        r.index.commit(
#            'Merge duplicates (manual) \n\n - using merge_duplicates.py')
#
#    duplicates_removed = nr_current_entries - len(bib_database.entries)
#    print('Duplicates removed: ' + str(duplicates_removed))
# print('')
