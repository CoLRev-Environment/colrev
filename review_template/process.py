#! /usr/bin/env python
import multiprocessing as mp
import os

import click
from bibtexparser.bibdatabase import BibDatabase

from review_template import dedupe
from review_template import importer
from review_template import init
from review_template import prepare
from review_template import repo_setup
from review_template import utils


DELAY_AUTOMATED_PROCESSING = repo_setup.config['DELAY_AUTOMATED_PROCESSING']

# Note: BATCH_SIZE can be as small as 1.
# Records should not be propagated/screened when the batch
# has not yet been committed
BATCH_SIZE = repo_setup.config['BATCH_SIZE']


def check_delay(db, min_status):
    if not DELAY_AUTOMATED_PROCESSING:
        return False

    cur_status = [x.get('status', 'NA') for x in db.entries]
    if 'imported' == min_status:
        if 'needs_manual_completion' in cur_status:
            return True
    if 'prepared' == min_status:
        if any(x in cur_status
               for x in ['imported', 'needs_manual_completion']):
            return True

    return False


class IteratorEx:
    def __init__(self, it):
        self.it = iter(it)
        self.sentinel = object()
        self.nextItem = next(self.it, self.sentinel)
        self.hasNext = self.nextItem is not self.sentinel

    def next(self):
        ret, self.nextItem = self.nextItem, next(self.it, self.sentinel)
        self.hasNext = self.nextItem is not self.sentinel
        return ret

    def __iter__(self):
        while self.hasNext:
            yield self.next()


current_batch = 0
batch_start = 1
batch_end = 0


def processing_condition(entry):
    global current_batch
    global batch_start
    global batch_end

    current_batch += 1
    batch_end += 1

    if current_batch >= BATCH_SIZE:
        current_batch = 0
        print(f'Processing entries {batch_start} to {batch_end}')
        batch_start = batch_end + 1
        return True

    # keep track of numbers...
    # last_record_i, prev_iteration_i = 0, 0
    # True if batch size is met (or if it is the last entry)
    # print information
    # if len(entry_batch) == BATCH_SIZE:
    # print('\n\nProcessing batch ' +
    #         str(max((last_record_i - BATCH_SIZE + 1),
    #                 prev_iteration_i+1)) +
    #         f' to {last_record_i} of ' +
    #         f'{len(all_entries)}')
    # prev_iteration_i = last_record_i

    # Note: do not count processed entries for batch size to avoid
    # removing entries from MAIN_REFERENCES
    # if entry.get('status', 'NA') != 'processed':
    #     last_record_i += 1

    return False


def set_citation_keys(db):
    citation_key_list = [entry['ID'] for entry in db.entries]
    for entry in db.entries:
        if 'imported' == entry['status']:
            entry.update(ID=utils.generate_citation_key_blacklist(
                entry, citation_key_list,
                entry_in_bib_db=True,
                raise_error=False))
            citation_key_list.append(entry['ID'])
    return db


def main():

    r = init.get_repo()
    utils.require_clean_repo(r)
    utils.build_docker_images()

    db = BibDatabase()
    entry_iterator = IteratorEx(importer.load_all_entries())
    for entry in entry_iterator:
        db.entries.append(entry)
        if entry_iterator.hasNext:
            if not processing_condition(entry):
                continue  # keep appending entries
        else:
            print('Processing entries')

        pool = mp.Pool(repo_setup.config['CPUS'])

        print('Import')
        db.entries = pool.map(importer.import_entry, db.entries)
        db = set_citation_keys(db)
        importer.create_commit(r, db)

        if check_delay(db, 'imported'):
            print('\nCompleted import step. To continue, use \n'
                  ' review_template man-complete '
                  '(for experts: disable DELAY_AUTOMATED_PROCESSING flag)\n\n')
            break

        print('Prepare')
        db.entries = pool.map(prepare.prepare, db.entries)
        prepare.create_commit(r, db)

        if check_delay(db, 'prepared'):
            print('\nCompleted preparation step. To continue, use \n'
                  ' review_template man-prep '
                  '(for experts: disable DELAY_AUTOMATED_PROCESSING flag)\n\n')
            break

        print('Process duplicates')
        pool.map(dedupe.append_merges, db.entries)
        db = dedupe.apply_merges(db)
        dedupe.create_commit(r, db)

        # TODO: meta_data_status (imported, prepared ,...) vs. record_status
        #  (pre-screen-excluded, included, ...) (what about the PDF?)?!?!

        # TODO, depending on REVIEW_STRATEGY:
        # minimal_review_pipeline: no screening/data extraction.
        # simply include all records, prepare, merge, acquire pdfs

        # db = utils.load_references_bib(
        #     modification_check=True, initialize=False,
        # )
        # acquire PDFs
        # backward search, ... (considering check_continue)
        # update_data()
        print()

    # to print tooltips (without replicating code from the pipeline repo)
    os.system('pre-commit run -a')

    return


@click.command()
def cli():
    main()
    return 0


if __name__ == '__main__':
    main()
