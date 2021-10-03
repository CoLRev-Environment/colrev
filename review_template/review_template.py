#! /usr/bin/env python
import multiprocessing as mp
import os

import click
import yaml

from review_template import cleanse_records
from review_template import entry_hash_function
from review_template import importer
from review_template import initialize
from review_template import process_duplicates
from review_template import utils

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']
DELAY_AUTOMATED_PROCESSING = \
    shared_config['params']['DELAY_AUTOMATED_PROCESSING']
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


def check_delay(bib_database, min_status):
    if not DELAY_AUTOMATED_PROCESSING:
        return False

    cur_status = [x.get('status', 'NA') for x in bib_database.entries]
    if 'imported' == min_status:
        if 'needs_manual_completion' in cur_status:
            return True
    if 'cleansed' == min_status:
        if any(x in cur_status
               for x in ['imported', 'needs_manual_completion']):
            return True

    return False


def process_entries(search_records, bib_database):
    global r

    pool = mp.Pool(CPUS)

    print('Import')
    [bib_database.entries.append(entry) for entry in search_records]
    # for entry in search_records:
    #     entry = importer.preprocess(entry)
    importer.create_commit(r, bib_database)

    if check_delay(bib_database, 'imported'):
        print('Stop processing (DELAY_AUTOMATED_PROCESSING flag)')
        return bib_database

    print('Cleanse')
    bib_database.entries = \
        pool.map(cleanse_records.cleanse, bib_database.entries)
    # for entry in to_cleanse:
    #     entry = (cleanse_records.cleanse(entry)
    cleanse_records.create_commit(r, bib_database)

    if check_delay(bib_database, 'cleansed'):
        print('Stop processing (DELAY_AUTOMATED_PROCESSING flag)')
        return bib_database

    print('Process duplicates')
    pool.map(process_duplicates.append_merges, bib_database.entries)
    # for entry in bib_database.entries:
    #     append_merges(entry)
    bib_database = process_duplicates.apply_merges(bib_database)
    process_duplicates.create_commit(r, bib_database)

    # TODO :continue (backward search, ...) considering check_continue(...)

    return bib_database


def main():

    global r
    r = initialize.get_repo()

    # Currently, citation_keys are generated
    # in importer.load()
    # We may discuss whether/how to generate new citation_keys
    # AND prevent conflicting citation_keys in parallel operation

    bib_database = utils.load_references_bib(True, initialize=True)

    # Complete the prior processing steps first
    if len(bib_database.entries) > 0:
        bib_database = process_entries([], bib_database)

    additional_search_records = importer.load(bib_database)

    if len(additional_search_records) < BATCH_SIZE:
        print('\n\nProcessing all records in one batch')
        bib_database = process_entries(additional_search_records, bib_database)
    else:
        last_record_i, prev_iteration_i, last_entry_id = 0, 0, 0
        search_record_batch = []
        if len(additional_search_records) > 0:
            last_entry_id = additional_search_records[-1]['ID']
        for entry in additional_search_records:
            search_record_batch.append(entry)
            last_record_i += 1
            if len(search_record_batch) == BATCH_SIZE or \
                    last_entry_id == entry['ID']:
                print('\n\nProcessing batch ' +
                      str(max((last_record_i - BATCH_SIZE + 1),
                              prev_iteration_i+1)) +
                      ' to ' + str(last_record_i) + ' of ' +
                      str(len(additional_search_records)))
                prev_iteration_i = last_record_i
                bib_database = process_entries(search_record_batch,
                                               bib_database)
                search_record_batch = []

    # TODO, depending on REVIEW_STRATEGY:
    # minimal_review_pipeline: no screening/data extraction.
    # simply include all records, cleanse, merge, acquire pdfs

    # bib_database = utils.load_references_bib(
    #     modification_check=True, initialize=False,
    # )
    # screen_sheet.update_screen(bib_database)
    # acquire PDFs
    # update_data()

    # to print tooltips (without replicating code from the pipeline repo)
    os.system('pre-commit run -a')

    return


@click.command()
def cli():
    main()
    return 0


if __name__ == '__main__':
    main()
