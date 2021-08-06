#! /usr/bin/env python
import csv
import itertools
import multiprocessing as mp
import os
import sys

import cleanse_records
import entry_hash_function
import importer
import initialize
import merge_duplicates
import pandas as pd
import screen_sheet
import utils
import yaml

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']
with open('private_config.yaml') as private_config_yaml:
    private_config = yaml.load(private_config_yaml, Loader=yaml.FullLoader)

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']
SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']

EMAIL = private_config['params']['EMAIL']
if 'CPUS' not in private_config['params']:
    CPUS = mp.cpu_count()-1
else:
    CPUS = private_config['params']['CPUS']

DEBUG_MODE = (1 == private_config['params']['DEBUG_MODE'])

# Note: BATCH_SIZE can be as small as 1.
# Records should not be propagated/screened when the batch
# has not yet been committed
if 'BATCH_SIZE' not in shared_config['params']:
    BATCH_SIZE = 500
else:
    BATCH_SIZE = shared_config['params']['BATCH_SIZE']

MERGING_NON_DUP_THRESHOLD = \
    shared_config['params']['MERGING_NON_DUP_THRESHOLD']
MERGING_DUP_THRESHOLD = shared_config['params']['MERGING_DUP_THRESHOLD']
REVIEW_STRATEGY = shared_config['params']['REVIEW_STRATEGY']


def initialize_duplicate_csvs():

    if not os.path.exists('duplicate_tuples.csv'):
        with open('duplicate_tuples.csv', 'a') as fd:
            fd.write('"ID1","ID2"\n')

    if not os.path.exists('non_duplicates.csv'):
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"ID"\n')

    if not os.path.exists('potential_duplicate_tuples.csv'):
        with open('potential_duplicate_tuples.csv', 'a') as fd:
            fd.write('"ID1","ID2","max_similarity"\n')

    return


def require_commited_MAIN_REFERENCES():
    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)]:
        print('Commit MAIN_REFERENCES before proceeding')
        sys.exit()
    return


def get_prev_queue(queue_order, hash_id):
    # Note: Because we only introduce individual (non-merged entries),
    # there should be no commas in hash_id!
    prev_entries = []
    for idx, el in enumerate(queue_order):
        if hash_id == el:
            prev_entries = queue_order[:idx]
            break
    return prev_entries


def cleanse(entry):

    if 'not_cleansed' == entry['status']:
        entry = cleanse_records.cleanse(entry)
    return entry


def append_merge_MAIN_REFERENCES_MERGED(entry, bib_database):

    if 'not_merged' != entry['status']:
        return

    # the order matters for the incremental merging (make sure that each
    # additional record is compared to/merged with all prior records in
    # the queue)
    with open('queue_order.csv', 'a') as fd:
        fd.write(entry['hash_id'] + '\n')
    queue_order = []
    with open('queue_order.csv') as read_obj:
        csv_reader = csv.reader(read_obj)
        for row in csv_reader:
            queue_order.append(row[0])
    required_prior_hash_ids = get_prev_queue(queue_order, entry['hash_id'])
    hash_ids_in_cleansed_file = []

    # note: no need to wait for completion of cleansing
    hash_ids_in_cleansed_file = [entry['hash_id'].split(',')
                                 for entry in bib_database.entries]
    hash_ids_in_cleansed_file = \
        list(itertools.chain(*hash_ids_in_cleansed_file))

    # if the entry is the first one added to the bib_database
    # (in a preceding processing step), it can be propagated
    if len(bib_database.entries) < 2:
        # entry.update(status = 'processed')
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
        return

    # Drop rows from references for which no hash_id is in
    # required_prior_hash_ids
    prior_entries = [x for x in bib_database.entries
                     if any(hash_id in x['hash_id'].split(',')
                            for hash_id in required_prior_hash_ids)]
    if len(prior_entries) < 1:
        return

    # get_similarities for each other entry
    references = pd.DataFrame.from_dict([entry] + prior_entries)

    # drop the same ID entry
    # Note: the entry is simply added as the first row.
    # references = references[~(references['ID'] == entry['ID'])]
    # dropping them before calculating similarities prevents errors
    # caused by unavailable fields!
    # Note: ignore entries that need manual cleansing in the merging
    # (until they have been cleansed!)
    references = \
        references[~references['status'].str.contains('needs_manual_cleansing',
                                                      na=False)]
    # means that all prior entries are tagged as needs_manual_cleansing
    if references.shape[0] == 0:
        # entry.update(status = 'processed')
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
        return
    references = \
        merge_duplicates.calculate_similarities_entry(references)

    max_similarity = references.similarity.max()
    citation_key = references.loc[references['similarity'].idxmax()]['ID']
    if max_similarity <= MERGING_NON_DUP_THRESHOLD:
        # Note: if no other entry has a similarity exceeding the threshold,
        # it is considered a non-duplicate (in relation to all other entries)
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
    if max_similarity > MERGING_NON_DUP_THRESHOLD and \
            max_similarity < MERGING_DUP_THRESHOLD:
        # The needs_manual_merging status is only set
        # for one element of the tuple!
        with open('potential_duplicate_tuples.csv', 'a') as fd:
            fd.write('"' + citation_key + '","' +
                     entry['ID'] + '","' + str(max_similarity) + '"\n')
    if max_similarity >= MERGING_DUP_THRESHOLD:
        # note: the following status will not be saved in the bib file but
        # in the duplicate_tuples.csv (which will be applied to the bib file
        # in the end)
        with open('duplicate_tuples.csv', 'a') as fd:
            fd.write('"' + citation_key + '","' + entry['ID'] + '"\n')

    return


def apply_merges():

    bib_database = utils.load_references_bib(
        modification_check=False, initialize=False,
    )

    # The merging also needs to consider whether citation_keys are propagated
    # Completeness of comparisons should be ensured by the
    # append_merge_MAIN_REFERENCES_MERGED procedure (which ensures that all
    # prior entries in global queue_order are considered before completing
    # the comparison/adding entries ot the csvs)

    merge_details = ''
    # Always merge clear duplicates: row[0] <- row[1]
    if os.path.exists('duplicate_tuples.csv'):
        with open('duplicate_tuples.csv') as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                hash_ids_to_merge = []
                for entry in bib_database.entries:
                    if entry['ID'] == row[1]:
                        print('drop ' + entry['ID'])
                        hash_ids_to_merge = entry['hash_id'].split(',')
                        # Drop the duplicated entry
                        bib_database.entries = \
                            [i for i in bib_database.entries
                             if not (i['ID'] == entry['ID'])]
                        break
                for entry in bib_database.entries:
                    if entry['ID'] == row[0]:
                        hash_ids = list(set(hash_ids_to_merge +
                                        entry['hash_id'].split(',')))
                        entry.update(hash_id=str(','.join(sorted(hash_ids))))
                        if 'not_merged' == entry['status']:
                            entry.update(status='processed')
                        merge_details += row[0] + ' < ' + row[1] + '\n'
                        break
        os.remove('duplicate_tuples.csv')

    # Set clear non-duplicates to completely processed (remove the status tag)
    if os.path.exists('non_duplicates.csv'):
        with open('non_duplicates.csv') as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                for entry in bib_database.entries:
                    if entry['ID'] == row[0]:
                        if 'not_merged' == entry['status']:
                            entry.update(status='processed')
        os.remove('non_duplicates.csv')

    # note: potential_duplicate_tuples need to be processed manually but we
    # tag the second entry (row[1]) as "needs_manual_merging"
    if os.path.exists('potential_duplicate_tuples.csv'):
        with open('potential_duplicate_tuples.csv') as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                for entry in bib_database.entries:
                    if entry['ID'] == row[1]:
                        entry.update(status='needs_manual_merging')
        potential_duplicates = \
            pd.read_csv('potential_duplicate_tuples.csv', dtype=str)
        potential_duplicates.sort_values(by=['max_similarity'],
                                         ascending=False, inplace=True)
        potential_duplicates.to_csv(
            'potential_duplicate_tuples.csv', index=False,
            quoting=csv.QUOTE_ALL, na_rep='NA',
        )

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    return merge_details


def append_to_screen(entry):
    with open(SCREEN, 'a') as fd:
        fd.write('"' + entry['ID'] + '","TODO","TODO",""\n')
        # Note: pandas read/write takes too long/may create conflicts!
    return


def process_entries(search_records, bib_database):

    pool = mp.Pool(CPUS)

    # NOTE: Problem: parallel processing does not store the status of records
    # (need to read files each time!)

    # parallel import
    print('Import')
    for entry in [entry for entry in search_records
                  if 'not_imported' == entry['status']]:
        entry = importer.preprocess(entry)
        del entry['source_file_path']
        bib_database.entries.append(entry)
    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    # import-commit
    # Note: details (e.g., commit details) should not be stored in memory
    # (they are lost when users interrupt the process)
    # TODO: add details to the commit message
    importer.create_commit(r, ['full_review mode'])

    # parallel cleansing
    print('Cleanse')
    bib_database.entries = pool.map(cleanse, bib_database.entries)
    # For non-parallel processing/debugging:
    # for entry in to_cleanse:
    #     cleanse(entry)
    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    # cleanse-commit
    cleanse_records.create_commit()

    # parallel merging
    print('Merge')
    pool.starmap(append_merge_MAIN_REFERENCES_MERGED,  [
                 [x, bib_database] for x in bib_database.entries])
    # For non-parallel processing/debugging:
    # for entry in bib_database.entries:
    #     print(entry['ID'])
    #     append_merge_MAIN_REFERENCES_MERGED(entry)
    merge_details = apply_merges()

    # merge commit
    merge_duplicates.create_commit(merge_details)

    return bib_database


def update_screen(bib_database):
    if not os.path.exists(SCREEN):
        screen_sheet.generate_screen_csv([])
        # Note: Users can include exclusion criteria afterwards

    screen = pd.read_csv(SCREEN, dtype=str)
    screened_records = screen['citation_key'].tolist()
    to_add = [entry['ID'] for entry in bib_database.entries
              if 'processed' == entry['status'] and
              entry['ID'] not in screened_records]
    for paper_to_screen in to_add:
        add_entry = pd.DataFrame({
            'citation_key': [paper_to_screen],
            'inclusion_1': ['TODO'],
            'inclusion_2': ['TODO'],
        })
        add_entry = add_entry.reindex(
            columns=screen.columns, fill_value='TODO',
        )
        add_entry['comment'] = '-'

        screen = pd.concat([screen, add_entry], axis=0, ignore_index=True)
    # To reformat/sort the screen:
    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(
        SCREEN, index=False,
        quoting=csv.QUOTE_ALL, na_rep='NA',
    )

    return


def print_tooltips(bib_database):
    to_cleanse_manually = [entry['ID']
                           for entry in bib_database.entries
                           if 'needs_manual_cleansing' == entry['status']]
    if len(to_cleanse_manually) > 0:
        print('\n\nEntries to cleanse manually (' +
              str(len(to_cleanse_manually)) +
              '), use\n\n   make cleanse_manual')
        print(' Note: remove the needs_manual_cleansing status')

    to_merge_manually = [entry['ID'] for entry in bib_database.entries
                         if 'needs_manual_merging' == entry['status']]
    if len(to_merge_manually) > 0:
        print('\nEntries to merge manually (' +
              str(len(to_merge_manually)) +
              '), use\n\n   make merge_manual\n')
    return


def remove_temporary_files():
    try:
        os.remove('queue_order.csv')
    except FileNotFoundError:
        pass
    return


def minimal_review_pipeline():
    # Explanation: no screening/data extraction, simply include all records,
    # cleanse, merge, acquire pdfs

    return


def full_review_pipeline():

    # Currently, citation_keys are generated
    # in importer.load()
    # We may discuss whether/how to generate new citation_keys
    # AND prevent conflicting citation_keys in parallel operation

    print('TODO: test repeated call of main.py')
    print('TODO: crowd-based merging')

    initialize_duplicate_csvs()

    all_search_records = importer.load()

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    last_record_i = 0
    search_record_batch = []
    last_entry_id = all_search_records[-1]['ID']
    for entry in all_search_records:
        search_record_batch.append(entry)
        last_record_i += 1
        if len(search_record_batch) == BATCH_SIZE or \
                last_entry_id == entry['ID']:
            print('\n\nProcessing batch ' +
                  str(last_record_i - BATCH_SIZE + 1) +
                  ' to ' + str(last_record_i))
            bib_database = process_entries(search_record_batch, bib_database)
            search_record_batch = []

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    update_screen(bib_database)

    # TODO: acquire PDFs

    # update_data()

    print_tooltips(bib_database)

    return


if __name__ == '__main__':

    # Explanation: each record should have status information
    # (at the end, no status information indicates that all processing steps
    # have been completed)each record is propagated as far as possible
    # (stopping as needs_manual_cleansing or needs_manual_merging if necessary)
    #
    # not_imported
    #     🡻
    # not_cleansed
    #     🡻   🢆
    #     🡻    needs_manual_cleansing
    #     🡻   🢇
    # not_merged
    #     🡻   🢆
    #     🡻    needs_manual_merging
    #     🡻   🢇
    # processed
    #

    process = {'minimal_review': minimal_review_pipeline,
               'full_review': full_review_pipeline}

    r = initialize.initialize_repo()

    # the REVIEW_STRATEGY is set in the shared config
    process[REVIEW_STRATEGY]()

    remove_temporary_files()
