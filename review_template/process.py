#! /usr/bin/env python
import os

import click

from review_template import dedupe
from review_template import importer
from review_template import init
from review_template import pdf_check
from review_template import pdfs
from review_template import prepare
from review_template import repo_setup
from review_template import utils

# Records should not be propagated/screened when the batch
# has not yet been committed
DELAY_AUTOMATED_PROCESSING = repo_setup.config['DELAY_AUTOMATED_PROCESSING']


class DelayRequirement(Exception):
    pass


def check_delay(db, min_status_requirement):

    if 'imported' == min_status_requirement:
        if len(db.entries) == 0:
            print('No search results available for import.')
            raise DelayRequirement

    if not DELAY_AUTOMATED_PROCESSING:
        return False

    cur_status = [x.get('status', 'NA') for x in db.entries]

    prior_status = ['imported', 'needs_manual_preparation']
    if 'prepared' == min_status_requirement:
        if any(x in cur_status for x in prior_status):
            print('\nCompleted preparation step. To continue, use \n'
                  ' review_template man-prep.\n\n')
            raise DelayRequirement

    prior_status.append('prepared')
    prior_status.append('needs_manual_merging')
    if 'processed' == min_status_requirement:
        if any(x in cur_status for x in prior_status):
            print('\nCompleted duplicate removal step. To continue, use \n'
                  ' review_template man-dedupe.\n\n')
            raise DelayRequirement

    cur_pdf_status = ['pdf_' + x.get('pdf_status', 'NA') for x in db.entries]

    prior_pdf_status = []
    if 'pdf_needs_retrieval' == min_status_requirement:
        if any(x in cur_pdf_status for x in prior_pdf_status) or \
                any(x in cur_status for x in prior_status):
            print('\nCompleted PDF retrieval. To continue, use \n'
                  ' review_template retrieve-pdf-manually (TODO).\n\n')
            raise DelayRequirement

    # Note: we can proceed if pdf_not_available
    prior_pdf_status.append('pdf_needs_manual_preparation')
    if 'pdf_needs_preparation' == min_status_requirement:
        if any(x in cur_pdf_status for x in prior_pdf_status) or \
                any(x in cur_status for x in prior_status):
            raise DelayRequirement

    return False


def main():

    repo = init.get_repo()
    utils.require_clean_repo(repo, ignore_pattern='search/')
    utils.build_docker_images()

    try:
        db = importer.import_entries(repo)

        db = prepare.prepare_entries(db, repo)

        db = dedupe.dedupe_entries(db, repo)

        db = pdfs.acquire_pdfs(db, repo)

        db = pdf_check.prepare_pdfs(db, repo)

        # Note: the checks for delaying the screen
        # are implemented in the screen.py

    except DelayRequirement:
        pass

    print()
    os.system('pre-commit run -a')

    return 0


@click.command()
def cli():
    main()
    return 0


if __name__ == '__main__':
    main()
