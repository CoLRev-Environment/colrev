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

    if 'prepared' == min_status:
        if any(x in cur_status
               for x in ['imported', 'needs_manual_preparation']):
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

    repo = init.get_repo()
    utils.require_clean_repo(repo, ignore_pattern='search/')
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
        importer.create_commit(repo, db)

    if len(db.entries) == 0:
        print('No search results available for import.')
        return

    # comment on check_delay/DELAY_AUTOMATED_PROCESSING:
    # we assume that import always succeeds. this means that we only have to
    # check for delayed processing after preparation (which may not succeed)
    # if check_delay(db, 'imported'):
    #     print('\nCompleted import step. To continue, use \n'
    #           ' review_template man-complete '
    #           '(for experts: disable DELAY_AUTOMATED_PROCESSING flag)\n\n')
    #     break

    # TODO: how to ensure BATCH_SIZE in the following processing steps?

    print('Prepare')
    pool = mp.Pool(repo_setup.config['CPUS'])
    db.entries = pool.map(prepare.prepare, db.entries)
    prepare.create_commit(repo, db)

    if check_delay(db, 'prepared'):
        print('\nCompleted preparation step. To continue, use \n'
              ' review_template man-prep '
              '(for experts: disable DELAY_AUTOMATED_PROCESSING flag)\n\n')
        os.system('pre-commit run -a')
        return

    print('Process duplicates')
    pool = mp.Pool(repo_setup.config['CPUS'])
    pool.map(dedupe.append_merges, db.entries)
    db = dedupe.apply_merges(db)
    dedupe.create_commit(repo, db)

    # TBD. screen, acquire_pdfs, ...?

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
