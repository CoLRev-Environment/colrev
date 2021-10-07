#! /usr/bin/env python
import configparser
import multiprocessing as mp
import os

import click

from review_template import dedupe
from review_template import entry_hash_function
from review_template import importer
from review_template import init
from review_template import prepare
from review_template import utils

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']

DELAY_AUTOMATED_PROCESSING = \
    config.getboolean('general', 'DELAY_AUTOMATED_PROCESSING')

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']
SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


# Note: BATCH_SIZE can be as small as 1.
# Records should not be propagated/screened when the batch
# has not yet been committed
BATCH_SIZE = config.getint('general', 'BATCH_SIZE', fallback=500)


def check_delay(bib_database, min_status):
    if not DELAY_AUTOMATED_PROCESSING:
        return False

    cur_status = [x.get('status', 'NA') for x in bib_database.entries]
    if 'imported' == min_status:
        if 'needs_manual_completion' in cur_status:
            return True
    if 'prepared' == min_status:
        if any(x in cur_status
               for x in ['imported', 'needs_manual_completion']):
            return True

    return False


def process_entries(search_records, bib_database):
    global r
    pool = mp.Pool(config.getint('general', 'CPUS', fallback=mp.cpu_count()-1))

    print('Import')
    [bib_database.entries.append(entry) for entry in search_records]
    importer.create_commit(r, bib_database)

    if check_delay(bib_database, 'imported'):
        print('Stop processing (DELAY_AUTOMATED_PROCESSING flag)\n\n')
        return bib_database

    print('Prepare')
    bib_database.entries = \
        pool.map(prepare.prepare, bib_database.entries)
    prepare.create_commit(r, bib_database)

    if check_delay(bib_database, 'prepared'):
        print('Stop processing (DELAY_AUTOMATED_PROCESSING flag)\n\n')
        return bib_database

    print('Process duplicates')
    pool.map(dedupe.append_merges, bib_database.entries)
    bib_database = dedupe.apply_merges(bib_database)
    dedupe.create_commit(r, bib_database)

    # TODO, depending on REVIEW_STRATEGY:
    # minimal_review_pipeline: no screening/data extraction.
    # simply include all records, prepare, merge, acquire pdfs

    # bib_database = utils.load_references_bib(
    #     modification_check=True, initialize=False,
    # )
    # acquire PDFs
    # backward search, ... (considering check_continue)
    # update_data()
    print()

    return bib_database


def main():

    global r
    r = init.get_repo()
    utils.build_docker_images()

    # Currently, citation_keys are generated
    # in importer.load()
    # We may discuss whether/how to generate new citation_keys
    # AND prevent conflicting citation_keys in parallel operation

    bib_database = utils.load_references_bib(True, initialize=True)
    additional_search_records = importer.load(bib_database)
    bib_database.entries = [x for x in bib_database.entries
                            if x.get('status', 'NA') == 'processed']

    if len(additional_search_records) < BATCH_SIZE:
        print('\nProcessing all records in one batch')
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
                      f' to {last_record_i} of ' +
                      f'{len(additional_search_records)}')
                prev_iteration_i = last_record_i
                bib_database = \
                    process_entries(search_record_batch, bib_database)
                search_record_batch = []

    # to print tooltips (without replicating code from the pipeline repo)
    os.system('pre-commit run -a')

    return


@click.command()
def cli():
    main()
    return 0


if __name__ == '__main__':
    main()
