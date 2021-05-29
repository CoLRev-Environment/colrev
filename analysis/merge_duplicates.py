#! /usr/bin/env python
import re
import sys

import dictdiffer
import git
import numpy as np
import pandas as pd
import utils
from fuzzywuzzy import fuzz
from tqdm import tqdm

nr_entries_added = 0
nr_current_entries = 0


def store_changes(references, bib_database):
    # convert the dataframe back to a list of dicts, assign to bib_database
    ref_list = references.drop(columns='similarity').to_dict('records')
    for idx, my_dict in enumerate(ref_list):
        ref_list[idx] = {k: str(v)
                         for k, v in my_dict.items() if str(v) != 'nan'}
    bib_database.entries = ref_list
    utils.save_bib_file(bib_database, 'data/references.bib')

    return


def remove_entry(references, citation_key):

    references = \
        references.drop(references[references['ID'] == citation_key].index)

#    # Note: not needed when operating with pandas dataframes!
#    for i in range(len(bib_database.entries)):
#        if bib_database.entries[i]['ID'] == citation_key:
#            bib_database.entries.remove(bib_database.entries[i])
#            break
    return references


def get_similarity(df_a, df_b):

    authors_a = re.sub(r'[^A-Za-z0-9, ]+', '', str(df_a['author']).lower())
    authors_b = re.sub(r'[^A-Za-z0-9, ]+', '', str(df_b['author']).lower())
    author_similarity = fuzz.ratio(authors_a, authors_b)/100

    # partial ratio (catching 2010-10 or 2001-2002)
    year_similarity = \
        fuzz.partial_ratio(str(df_a['year']), str(df_b['year']))/100

    journal_a = re.sub(r'[^A-Za-z0-9 ]+', '', str(df_a['journal']).lower())
    journal_b = re.sub(r'[^A-Za-z0-9 ]+', '', str(df_b['journal']).lower())
    journal_similarity = fuzz.ratio(journal_a, journal_b)/100

    title_a = re.sub(r'[^A-Za-z0-9, ]+', '', str(df_a['title']).lower())
    title_b = re.sub(r'[^A-Za-z0-9, ]+', '', str(df_b['title']).lower())
    title_similarity = fuzz.ratio(title_a, title_b)/100

    weights = [0.15, 0.75, 0.05, 0.05]
    similarities = [author_similarity,
                    title_similarity,
                    year_similarity,
                    journal_similarity]
    weighted_average = sum(similarities[g] * weights[g]
                           for g in range(len(similarities)))

    return weighted_average


def calculate_similarities(references, duplicate_min_similarity_threshold):
    nr_entries = references.shape[0]
    SimilarityArray = np.zeros([nr_entries, nr_entries])

    # Fill out the similarity matrix first
    for base_entry_index, base_entry in \
            tqdm(references.iterrows(), total=references.shape[0]):
        references['similarity'] = 0
        for comparison_entry_index, comparison_entry in references.iterrows():
            if base_entry_index > comparison_entry_index:
                SimilarityArray[base_entry_index, comparison_entry_index] = \
                    get_similarity(base_entry, comparison_entry)

    tuples_to_process = []
    maximum_similarity = 1
    while True:

        maximum_similarity = np.amax(SimilarityArray)
        if maximum_similarity < duplicate_min_similarity_threshold:
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
                if first_propagated:  # remove the second one

                    existing_hash_ids = \
                        references.loc[references['ID'] ==
                                       tuples[i][0]]['hash_id'].values[0]
                    hash_ids_to_add = \
                        references.loc[references['ID'] ==
                                       tuples[i][1]]['hash_id'].values[0]
                    combined_hash_list = set(hash_ids_to_add.split(',')
                                             + existing_hash_ids.split(','))

                    references.at[references['ID'] == tuples[i][0],
                                  'hash_id'] = ','.join(combined_hash_list)

                    references = remove_entry(references, tuples[i][1])
                    tuples[i][3] = 'merged'

                if second_propagated:  # remove the first one
                    existing_hash_ids = \
                        references.loc[references['ID'] ==
                                       tuples[i][1]]['hash_id'].values[0]
                    hash_ids_to_add = \
                        references.loc[references['ID'] ==
                                       tuples[i][0]]['hash_id'].values[0]
                    combined_hash_list = set(hash_ids_to_add.split(',')
                                             + existing_hash_ids.split(','))

                    references.at[references['ID'] == tuples[i][1],
                                  'hash_id'] = ','.join(combined_hash_list)

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


def interactively_merge_entries(references, tuples):

    print('TODO: check whether hash-id mappings were classified ',
          'as non-duplicates before')
    input('TODO: add hash_ids / unique')

    for i in range(len(tuples)):
        first_propagated = utils.propagated_citation_key(tuples[i][0])
        second_propagated = utils.propagated_citation_key(tuples[i][1])

        if tuples[i][3] in ['merged', 'skipped', 'propagation_problem']:
            continue

        if first_propagated and second_propagated:
            print('WARNING: both citation_keys propagated: ',
                  tuples[i][0],
                  ', ',
                  tuples[i][1])
            tuples[i][3] = 'propagation_problem'
            continue
        else:
            decision = ''
            while decision not in ['y', 'n']:
                print()
                print()
                print('------------------')
                print(tuples[i])
                print()

                base_entry = references.loc[references['ID'] == tuples[i][0]]\
                                       .to_dict('records')
                comparison_entry = \
                    references.loc[references['ID'] == tuples[i][1]]\
                    .to_dict('records')

                [print(x) for x in dictdiffer.diff(base_entry,
                                                   comparison_entry)]

                decision = input('Duplicate (y/n)?')

            if 'n' == decision:
                tuples[i][3] = 'no_duplicate'
                print('TODO: save hash-id mapping for non-duplicates')

                continue

            try:
                if first_propagated:  # remove the second one

                    existing_hash_ids = \
                        references.loc[references['ID'] ==
                                       tuples[i][0]]['hash_id'].values[0]
                    hash_ids_to_add = \
                        references.loc[references['ID'] ==
                                       tuples[i][1]]['hash_id'].values[0]
                    combined_hash_list = set(hash_ids_to_add.split(',')
                                             + existing_hash_ids.split(','))

                    references.at[references['ID'] == tuples[i][0],
                                  'hash_id'] = ','.join(combined_hash_list)

                    references = remove_entry(references, tuples[i][1])
                    tuples[i][3] = 'merged'

                if second_propagated:  # remove the first one
                    existing_hash_ids = \
                        references.loc[references['ID'] ==
                                       tuples[i][1]]['hash_id'].values[0]
                    hash_ids_to_add = \
                        references.loc[references['ID'] ==
                                       tuples[i][0]]['hash_id'].values[0]
                    combined_hash_list = set(hash_ids_to_add.split(',')
                                             + existing_hash_ids.split(','))

                    references.at[references['ID'] == tuples[i][1],
                                  'hash_id'] = ','.join(combined_hash_list)

                    references = remove_entry(references, tuples[i][0])
                    tuples[i][3] = 'merged'
            except IndexError:
                # cases in which multiple entries have a high similarity
                # and the first ones have already been removed from references
                # creating an IndexError in the references[....].values[0]
                tuples[i][3] = 'skipped'
                pass
        print(tuples[i])

    return references, tuples


if __name__ == '__main__':

    print('')
    print('')

    print('Merge duplicates')

    r = git.Repo('data')

    if r.is_dirty():
        print('Commit files before merging duplicates.')
        sys.exit()

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    # print('Remove the following restriction:')
    # bib_database.entries = bib_database.entries[:100]

    references = pd.DataFrame.from_dict(bib_database.entries)

    duplicate_min_similarity_threshold = 0.8
    SimilarityArray, tuples_to_process = \
        calculate_similarities(references, duplicate_min_similarity_threshold)

#    nr_current_entries = len(bib_database.entries)
#
#    print(str(nr_current_entries) + ' records in references.bib')

    print('TODO: check whether hash-id mappings were classified as ',
          'non-duplicates before (and update tuples_to_process accordingly)')

    auto_threshold = 1.0
    # merge identical entries (ie., similarity = 1)
    references, tuples_to_process = auto_merge_entries(references,
                                                       tuples_to_process,
                                                       auto_threshold)

    store_changes(references, bib_database)

    # create a commit if there are changes (removed duplicates)
    if 'references.bib' in [item.a_path for item in r.index.diff(None)]:
        r.index.add(['references.bib'])
        # r.index.add(['search/bib_details.csv'])
        r.index.commit(
            'Merge duplicates (script)',
            author=git.Actor('script:merge_duplicates.py (automated)', ''),
        )

    references, tuples_to_process = \
        interactively_merge_entries(references,
                                    tuples_to_process)

    store_changes(references, bib_database)

    # create a commit if there are changes (removed duplicates)
    if 'references.bib' in [item.a_path for item in r.index.diff(None)]:
        r.index.add(['references.bib'])
        # r.index.add(['search/bib_details.csv'])
        r.index.commit(
            'Merge duplicates (manual) \n\n - using merge_duplicates.py')

    print('TODO: update get_similarity: ',
          'consider issue, volume, pages, booktitle (sensitivity: editorials?')

#    duplicates_removed = nr_current_entries - len(bib_database.entries)
#    print('Duplicates removed: ' + str(duplicates_removed))
#    print('')
