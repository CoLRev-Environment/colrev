#! /usr/bin/env python
import logging
import os

import click
import git

from review_template import dedupe
from review_template import importer
from review_template import init
from review_template import pdf_check
from review_template import pdfs
from review_template import prepare
from review_template import repo_setup
from review_template import status
from review_template import utils

# Records should not be propagated/screened when the batch
# has not yet been committed
DELAY_AUTOMATED_PROCESSING = repo_setup.config['DELAY_AUTOMATED_PROCESSING']


def reprocess_id(id, repo):
    if id is None:
        return

    MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

    if 'all' == id:
        logging.info('Removing/reprocessing all entries')
        com_msg = '⚙️ Reprocess all entries'
        os.remove(MAIN_REFERENCES)
        repo.index.remove([MAIN_REFERENCES], working_tree=True)

    else:
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        com_msg = '⚙️ Reprocess ' + id
        bib_database.entries = [
            x for x in bib_database.entries if id != x['ID']]
        utils.save_bib_file(bib_database, MAIN_REFERENCES)
        repo.index.add([MAIN_REFERENCES])

    repo.index.commit(
        com_msg + utils.get_version_flag() +
        utils.get_commit_report(os.path.basename(__file__)),
        author=git.Actor('script:process.py', ''),
        committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                            repo_setup.config['EMAIL']),
    )
    logging.info(f'Created commit ({com_msg})')
    print()
    with open('report.log', 'r+') as f:
        f.truncate(0)
    return


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


def main(reprocess_ids=None):

    status.repository_validation()
    repo = init.get_repo()
    utils.require_clean_repo(repo, ignore_pattern='search/')
    utils.build_docker_images()
    reprocess_id(reprocess_ids, repo)

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
