#! /usr/bin/env python
import csv
import os
import re

import bibtexparser
import entry_hash_function
import git
import numpy as np
import pandas as pd
import reformat_bibliography
import utils
import yaml
from bibtexparser.customization import convert_to_unicode
from fuzzywuzzy import fuzz
from tqdm import tqdm
# import dictdiffer

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
MAIN_REFERENCES_CLEANSED = MAIN_REFERENCES.replace('.bib', '_cleansed.bib')

pd.options.mode.chained_assignment = None  # default='warn'


def store_changes(references, bib_database):
    # convert the dataframe back to a list of dicts, assign to bib_database
    # .drop(columns='similarity')
    ref_list = references.to_dict('records')
    for idx, my_dict in enumerate(ref_list):
        ref_list[idx] = {k: str(v)
                         for k, v in my_dict.items() if str(v) != 'nan'}
    bib_database.entries = ref_list

    return bib_database


def remove_entry(references, citation_key):

    references = \
        references.drop(references[references['ID'] == citation_key].index)

#    # Note: not needed when operating with pandas dataframes!
#    for i in range(len(bib_database.entries)):
#        if bib_database.entries[i]['ID'] == citation_key:
#            bib_database.entries.remove(bib_database.entries[i])
#            break
    return references


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

    references['container_title'] = references['journal'] + \
        references['booktitle'] + \
        references['series']

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


def calculate_similarities(SimilarityArray, references, min_similarity):

    # Fill out the similarity matrix first
    for base_entry_i in tqdm(range(1, references.shape[0])):
        for comparison_entry_i in range(1, references.shape[0]):
            if base_entry_i > comparison_entry_i:
                if -1 != SimilarityArray[base_entry_i, comparison_entry_i]:
                    SimilarityArray[base_entry_i, comparison_entry_i] = \
                        get_similarity(
                            references.iloc[base_entry_i],
                            references.iloc[comparison_entry_i])

    tuples_to_process = []
    maximum_similarity = 1
    while True:

        maximum_similarity = np.amax(SimilarityArray)
        if maximum_similarity < min_similarity:
            break
        result = np.where(SimilarityArray == np.amax(SimilarityArray))
        listOfCordinates = list(zip(result[0], result[1]))
        for cord in listOfCordinates:
            SimilarityArray[cord] = 0  # ie., has been processed
            tuples_to_process.append([references.iloc[cord[0]]['ID'],
                                      references.iloc[cord[1]]['ID'],
                                      maximum_similarity,
                                      'not_processed'])

    return SimilarityArray, tuples_to_process


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


def auto_merge_entries(references, tuples, threshold):

    for i in range(len(tuples)):
        if tuples[i][2] < threshold:
            continue
        first_propagated = utils.propagated_citation_key(tuples[i][0])
        second_propagated = utils.propagated_citation_key(tuples[i][1])

        if first_propagated and second_propagated:
            print('WARNING: both citation_keys propagated: ',
                  tuples[i][0],
                  ', ',
                  tuples[i][1])
            tuples[i][3] = 'propagation_problem'
            continue
        else:
            try:

                if not first_propagated and not second_propagated:

                    # Use the entry['ID'] without appended letters if possible
                    # Set first_propagated=True if entry['ID']
                    # should be kept for the first entry
                    if tuples[i][0][-1:].isnumeric() and \
                       not tuples[i][1][-1:].isnumeric():
                        first_propagated = True
                    else:
                        second_propagated = True
                        # This arbitrarily uses the second entry['ID']
                        # if none of the IDs has a letter appended.

                if first_propagated:  # remove the second one
                    combined_hash_list = get_combined_hash_id_list(references,
                                                                   tuples[i])
                    references.at[references['ID'] == tuples[i][0],
                                  'hash_id'] = combined_hash_list

                    references = remove_entry(references, tuples[i][1])
                    tuples[i][3] = 'merged'

                if second_propagated:  # remove the first one
                    combined_hash_list = get_combined_hash_id_list(references,
                                                                   tuples[i])

                    references.at[references['ID'] == tuples[i][1],
                                  'hash_id'] = combined_hash_list

                    references = remove_entry(references, tuples[i][0])
                    tuples[i][3] = 'merged'
            except IndexError:
                # cases in which multiple entries have a high similarity
                # and the first ones have already been removed from references
                # creating an IndexError in the references[....].values[0]
                tuples[i][3] = 'skipped'
                pass
        # print(tuples[i])

    return references, tuples


def update_entries_considered_non_duplicates(SimilarityArray, references):

    # If a case-by-case decisions is preferred
    # consider_non_duplicated = []
    # for bib_file in utils.get_bib_files():
    #     print(bib_file)
    #     non_duplicated = input('consider non-duplicates? (y/n)')
    #     if 'y' == non_duplicated:
    #         consider_non_duplicated.append(bib_file)
    consider_non_duplicated = [os.path.basename(x)
                               for x in utils.get_bib_files()]

    for non_duplicated_bib in consider_non_duplicated:
        print('Skipping within-file duplices for ' + non_duplicated_bib)
        hash_id_list = []
        with open(os.path.join('search', non_duplicated_bib)) as bibtex_file:
            non_duplicated_bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True,
            ).parse_file(bibtex_file, partial=True)
            for entry in non_duplicated_bib_database.entries:
                hash_id = \
                    entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)
                hash_id_list.append(hash_id)

# All permutations within the bib file are considered non-duplicates
# NOTE: creating the list of permutations may require too much memory
# non_duplicated_hash_id_pairs = list(itertools.permutations(hash_id_list, 2))
# print(non_duplicated_hash_id_pairs)
# for hash_id, non_equivalent_hash_id in non_duplicated_hash_id_pairs:

            non_duplicated_indices = []
            for i, entry in references.iterrows():
                if any(x in str(entry.get('hash_id', 'NA')).split(',')
                       for x in hash_id_list):
                    non_duplicated_indices.append(i)

            for non_dup_ind1 in non_duplicated_indices:
                for non_dup_ind2 in non_duplicated_indices:
                    SimilarityArray[non_dup_ind1, non_dup_ind2] = -1

    return SimilarityArray


def update_known_non_duplicates(SimilarityArray, references):

    known_non_duplicates_df = pd.read_csv('merging.csv')
    known_non_duplicates = known_non_duplicates_df[
        known_non_duplicates_df['duplicate'] == 'no']['hash_id']

    for hash_id_pair in known_non_duplicates:
        hash_id_pair = hash_id_pair.split(',')
        for hash_id in hash_id_pair:
            # get indices of the other hash_ids and
            # set the corresponding similarity_array to 0
            for non_equivalent_hash_id in hash_id_pair:
                id1 = references.index[
                    references['hash_id'] == hash_id
                ].tolist()[0]

                id2 = references.index[
                    references['hash_id'] == non_equivalent_hash_id
                ].tolist()[0]

                SimilarityArray[id1, id2] = -1
                SimilarityArray[id2, id1] = -1

    return SimilarityArray


def merge_bib(bib_database):

    references = pd.DataFrame.from_dict(bib_database.entries)

    nr_entries = references.shape[0]
    SimilarityArray = np.zeros([nr_entries, nr_entries])

    SimilarityArray = update_entries_considered_non_duplicates(
        SimilarityArray, references)

    min_similarity = 0.7
    SimilarityArray, tuples_to_process = \
        calculate_similarities(SimilarityArray, references,
                               min_similarity)

    # set cells to -1 if the papers have been coded as non-duplicates
    input('TODO: reinclude the following')
    # SimilarityArray = update_known_non_duplicates(SimilarityArray,references)

    # nr_current_entries = len(bib_database.entries)
    # print(str(nr_current_entries) + ' records in ' + MAIN_REFERENCES)

    print('TODO: check whether hash-id mappings were classified as ',
          'non-duplicates before (and update tuples_to_process accordingly)')

    # auto_threshold = 1.0
    # merge identical entries (ie., similarity = 1)
    # references, tuples_to_process = auto_merge_entries(references,
    #                                                    tuples_to_process,
    #                                                    auto_threshold)
    #
    # store_changes(references, bib_database)
    # r.index.add([MAIN_REFERENCES])

    print('TODO: we could implement a loop here - iteratively lowering ')
    print('the threshold, checking/adding to index and repeating')

    # no errors with a 0.95 threshold.
    auto_threshold = 0.95
    references, tuples_to_process = auto_merge_entries(references,
                                                       tuples_to_process,
                                                       auto_threshold)

    tuples_df = pd.DataFrame.from_dict(tuples_to_process)

    tuples_df.to_csv('tuples_for_merging.csv',
                     index=False, quoting=csv.QUOTE_ALL)

    bib_database = store_changes(references, bib_database)

    return bib_database


def create_commit(merge_details):

    # to avoid failing pre-commit hooks
    reformat_bibliography.reformat_bib()

    r = git.Repo('')
    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)]:
        r.index.add([MAIN_REFERENCES])
        if os.path.exists('potential_duplicate_tuples.csv'):
            r.index.add(['potential_duplicate_tuples.csv'])
        r.index.commit(
            'Merge duplicates (script)' + '\nDuplicates removed: \n' +
            merge_details,
            author=git.Actor('script:merge_duplicates.py (automated)', ''),
        )
    return


def manual_merge_commit():
    r = git.Repo('')
    r.index.add([MAIN_REFERENCES])
    hook_skipping = 'false'
    if not DEBUG_MODE:
        hook_skipping = 'true'

    r.index.commit(
        'Cleanse manual ' + MAIN_REFERENCES,
        author=git.Actor('manual:merge duplicates', ''),
        skip_hooks=hook_skipping
    )
    print('Created commit: Merge manual ' + MAIN_REFERENCES)

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
