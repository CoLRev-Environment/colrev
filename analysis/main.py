#! /usr/bin/env python
import csv
import itertools
import multiprocessing as mp
import os
import sys
import time
from time import gmtime
from time import strftime

import bibtexparser
import cleanse_records
import config
import entry_hash_function
import git
import importer
import merge_duplicates
import pandas as pd
import reformat_bibliography
import screen_sheet
import utils
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode
from tqdm import tqdm

MAIN_REFERENCES = entry_hash_function.paths['MAIN_REFERENCES']
EMAIL = config.details['EMAIL']
SCREEN = entry_hash_function.paths['SCREEN']

MAIN_REFERENCES_CLEANSED = MAIN_REFERENCES.replace('.bib', '_cleansed.bib')


def load_bib_writer():

    writer = BibTexWriter()

    writer.contents = ['entries', 'comments']
    writer.indent = '  '
    writer.display_order = [
        'author',
        'booktitle',
        'journal',
        'title',
        'year',
        'editor',
        'number',
        'pages',
        'series',
        'volume',
        'abstract',
        'book-author',
        'book-group-author',
        'doi',
        'file',
        'hash_id',
    ]
    writer.order_entries_by = ('ID', 'author', 'year')
    writer.add_trailing_comma = True
    writer.align_values = True

    return writer


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


def traditional_pipeline():
    # Explanation: complete each step for all entries, commit, and proceed

    return


def traditional_delay_manual():

    # Explanation: like traditional_pipeline, but the manual steps are delayed

    return


def append_to_MAIN_REFERENCES(entry):

    del entry['source_file_path']
    db = BibDatabase()
    db.entries = [entry]
    bibtex_str = bibtexparser.dumps(db, writer)
    with open(MAIN_REFERENCES, 'a') as myfile:
        myfile.write(bibtex_str)

    return


def append_to_MAIN_REFERENCES_CLEANSED(entry):

    db = BibDatabase()
    db.entries = [entry]
    bibtex_str = bibtexparser.dumps(db, writer)
    with open(MAIN_REFERENCES_CLEANSED, 'a') as myfile:
        myfile.write(bibtex_str)

    return


def append_merge_MAIN_REFERENCES_MERGED(entry):

    if 'needs_manual_cleansing' == entry['status']:
        # Note: The needs_manual_cleansing entries should be appended
        # (and ignored in the cleansing!)
        return entry

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
    # Ensure that all prior entries are available (for parallel processing)
    max_iterations = 0
    with open(MAIN_REFERENCES_CLEANSED) as target_db:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(target_db, partial=True)
    while not all(hash_id in required_prior_hash_ids
                  for hash_id in hash_ids_in_cleansed_file):
        max_iterations += 1
        time.sleep(1)
        # load prior entries (according to the queue) that are cleansed
        with open(MAIN_REFERENCES_CLEANSED) as target_db:
            bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True,
            ).parse_file(target_db, partial=True)

        hash_ids_in_cleansed_file = [entry['hash_id'].split(',')
                                     for entry in bib_database]
        hash_ids_in_cleansed_file = \
            list(itertools.chain(*hash_ids_in_cleansed_file))
        if max_iterations > 20:
            return entry

    # if the entry is the first one inserted into the cleansed bib_database
    # (in a preceding processing step), it can be propagated
    if len(bib_database.entries) < 2:
        entry['status'] = 'processed'
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
        return entry

    # get_similarities for each other entry
    references = pd.DataFrame.from_dict(bib_database.entries)

    # TODO: drop rows from references for which
    # no hash_id is in required_prior_hash_ids

    # drop the same ID entry
    references = references[~(references['ID'] == entry['ID'])]
    # dropping them before calculating similarities prevents errors
    # caused by unavailable fields!
    # Note: ignore entries that need manual cleansing in the merging
    # (until they have been cleansed!)
    references = \
        references[~references['status'].str.contains('needs_manual_cleansing',
                                                      na=False)]
    # means that all prior entries are tagged as needs_manual_cleansing
    if references.shape[0] == 0:
        entry['status'] = 'processed'
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
        return entry
    references = \
        merge_duplicates.calculate_similarities_entry(references, entry)

    max_similarity = references.similarity.max()
    citation_key = references.loc[references['similarity'].idxmax()]['ID']
    if max_similarity <= 0.7:
        entry['status'] = 'processed'
        # Note: if no other entry has a similarity exceeding the threshold,
        # it is considered a non-duplicate (in relation to all other entries)
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
    if max_similarity > 0.7 and \
            max_similarity < 0.95:
        # The needs_manual_merging status is only set
        # for one element of the tuple!
        entry['status'] = 'needs_manual_merging'
        with open('potential_duplicate_tuples.csv', 'a') as fd:
            fd.write('"' + citation_key + '","' +
                     entry['ID'] + '","' + str(max_similarity) + '"\n')
    if max_similarity >= 0.95:
        # note: the following status will not be saved in the bib file but
        # in the duplicate_tuples.csv (which will be applied to the bib file
        # in the end)
        entry['status'] = 'merged'
        with open('duplicate_tuples.csv', 'a') as fd:
            fd.write('"' + citation_key + '","' + entry['ID'] + '"\n')

    return entry


def apply_merges():

    bib_database = utils.load_references_bib(
        modification_check=False, initialize=False,
    )

    # The merging also needs to consider whether citation_keys are propagated
    # Completeness of comparisons should be ensured by the
    # append_merge_MAIN_REFERENCES_MERGED procedure (which ensures that all
    # prior entries in global queue_order are considered before completing
    # the comparison/adding entries ot the csvs)

    # Always merge clear duplicates: row[0] <- row[1]
    with open('duplicate_tuples.csv') as read_obj:
        csv_reader = csv.reader(read_obj)
        print('duplicate_tuples')
        for row in csv_reader:
            hash_ids_to_merge = []
            for entry in bib_database.entries:
                if entry['ID'] == row[1]:
                    print('drop ' + entry['ID'])
                    hash_ids_to_merge = entry['hash_id'].split(',')
                    # Drop the duplicated entry
                    bib_database.entries = [i for i in bib_database.entries
                                            if not (i['ID'] == entry['ID'])]
                    break
            for entry in bib_database.entries:
                if entry['ID'] == row[0]:
                    hash_ids = list(set(hash_ids_to_merge +
                                    entry['hash_id'].split(',')))
                    entry['hash_id'] = str(','.join(sorted(hash_ids)))
                    if 'not_merged' == entry['status']:
                        entry['status'] = 'processed'
                    break
    os.remove('duplicate_tuples.csv')

    # Set clear non-duplicates to completely processed (remove the status tag)
    with open('non_duplicates.csv') as read_obj:
        csv_reader = csv.reader(read_obj)
        for row in csv_reader:
            for entry in bib_database.entries:
                if entry['ID'] == row[0]:
                    if 'not_merged' == entry['status']:
                        entry['status'] = 'processed'
    os.remove('non_duplicates.csv')

    # note: potential_duplicate_tuples need to be processed manually but we
    # tag the second entry (row[1]) as "needs_manual_merging"
    with open('potential_duplicate_tuples.csv') as read_obj:
        csv_reader = csv.reader(read_obj)
        entries_in_file = False
        for row in csv_reader:
            if row[0] != 'ID1':
                entries_in_file = True
            for entry in bib_database.entries:
                if entry['ID'] == row[1]:
                    entry['status'] = 'needs_manual_merging'
    if not entries_in_file:
        os.remove('potential_duplicate_tuples.csv')
    else:
        potential_duplicates = \
            pd.read_csv('potential_duplicate_tuples.csv', dtype=str)
        potential_duplicates.sort_values(by=['max_similarity'],
                                         ascending=False, inplace=True)
        potential_duplicates.to_csv(
            'potential_duplicate_tuples.csv', index=False,
            quoting=csv.QUOTE_ALL, na_rep='NA',
        )

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    return


def process_entry(entry):

    if 'not_imported' == entry['status']:
        entry = importer.preprocess(entry)
        append_to_MAIN_REFERENCES(entry)

    if 'not_cleansed' == entry['status']:
        entry = cleanse_records.cleanse(entry)

    # note: always append entry to REFERENCES_CLEANSED (regardless of the result/status)
    append_to_MAIN_REFERENCES_CLEANSED(entry)

    if 'not_merged' == entry['status']:
        entry = append_merge_MAIN_REFERENCES_MERGED(entry)
        # only add entries to screen once they have been processed completely
        # note: the record is added to the screening sheet when the not_merged
        # status changes to '' (this should only happen once)
        if 'processed' == entry['status']:
            with open(SCREEN, 'a') as fd:
                fd.write('"' + entry['ID'] + '","TODO","TODO",""\n')
            # Note: pandas read/write takes too long/may create conflicts!

    return


def living_review_pipeline():

    # Explanation: each record should have status information
    # (at the end, no status information indicates that all processing steps
    #  have been completed)each record is propagated as far as possible
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

    # Currently, citation_keys are generated
    # search_records = in importer.load()
    # We may discuss whether/how to generate new citation_keys
    # AND prevent conflicting citation_keys in parallel operation

    print('TODO: test repeated call of main.py ' +
          '(especially when stopping the process)' +
          'systematically check how to resume the process by ' +
          'leveraging status information!')

    print('TODO: merge_duplicates.py/get_similarity should consider ' +
          'container titles more generally (not just journals!)')

    print('TODO: crowd-based merging')

    create_commits = True

    # save changes to references.bib, references_cleansed.bib,
    # references_merged.bib
    # once the run is completed: commit, override changes and commit,
    # override changes and commit
    # afterwards: manual cleansing/merging
    # try:

    print('\n\n Import records')
    search_records = importer.load()

    pool = mp.Pool(mp.cpu_count()-2)
    print(strftime('%Y-%m-%d %H:%M:%S', gmtime()))
    for _ in tqdm(pool.imap_unordered(process_entry, search_records),
                  total=len(search_records)):
        pass
    print(strftime('%Y-%m-%d %H:%M:%S', gmtime()))

    # for entry in search_records:
    #     print('Processing entry: ' + entry['ID'])
    #     process_entry(entry)

    # except KeyboardInterrupt:
    #   https://stackoverflow.com/questions/11312525/catch-ctrlc-sigint-and-exit-multiprocesses-gracefully-in-python
    #     if 'y' != input('Create commits despite interruption? (y/n)'):
    #         print('Waiting for remaining workers to finish')
    #         time.sleep(20)
    #         create_commits = False
    #     pass

    try:
        os.remove('queue_order.csv')
    except FileNotFoundError:
        pass

    if create_commits:
        # to avoid failing pre-commit hooks
        reformat_bibliography.reformat_bib()
        # Note: details (e.g., commit details) should not be stored in memory
        # (they are lost when users interrupt the process)
        # TODO: add details to the commit message
        importer.create_commit(r, ['living_review mode'])
        os.remove(MAIN_REFERENCES)
        os.rename(MAIN_REFERENCES_CLEANSED, MAIN_REFERENCES)
        # to avoid failing pre-commit hooks
        reformat_bibliography.reformat_bib()
        cleanse_records.create_commit()
        apply_merges()
        # to avoid failing pre-commit hooks
        reformat_bibliography.reformat_bib()
        merge_duplicates.create_commit()

        # To reformat/sort the screen:
        screen = pd.read_csv(SCREEN, dtype=str)
        screen.sort_values(by=['citation_key'], inplace=True)
        screen.to_csv(
            SCREEN, index=False,
            quoting=csv.QUOTE_ALL, na_rep='NA',
        )

    # input('NOTE: it could be better to start with the merging and then ' +\
    #    'to the cleanse and merge again? (the tuples-csvs are based on ' +\
        # 'citation_keys that should not change!)')

    # bib_database = utils.load_references_bib(
    #         modification_check=False, initialize=False,
    # )
    # to_cleanse_manually = [entry['ID']
    #           for entry in bib_database.entries
    #           if 'needs_manual_cleansing' == entry['status']]
    # if len(to_cleanse_manually) > 0:
    #     print('\n Entries to cleanse manually: ' + \
    #   ','.join(to_cleanse_manually))
    #     print('Note: remove the needs_manual_cleansing status')
    # to_merge_manually = [entry['ID'] for entry in bib_database.entries
    #                   if 'needs_manual_merging' == entry['status']]
    # if len(to_merge_manually) > 0:
    #     print('\n Entries to merge manually: ' + ','.join(to_merge_manually))
    #     print('Note: remove the needs_manual_merging status')
    # print('During manual merging:' +\
    #       ' add non-duplicates to a separate field of the bib entry')

    return


if __name__ == '__main__':

    # initialize?
    assert utils.hash_function_up_to_date()
    r = git.Repo()
    writer = load_bib_writer()

    initialize_duplicate_csvs()
    if not os.path.exists(SCREEN):
        screen_sheet.generate_screen_csv([])
        # Note: Users can include exclusion criteria afterwards

    # get propagation_strategy from data directory (config parameter)
    strategy = 'living'

    process = {'traditional': traditional_pipeline,
               'traditional_delay_manual': traditional_delay_manual,
               'living': living_review_pipeline}

    process[strategy]()
