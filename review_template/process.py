#! /usr/bin/env python
import logging
import os

import click
import git

from review_template import dedupe
from review_template import importer
from review_template import init
from review_template import pdf_prepare
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

    # all entries need to have at least the min_status_requirement (or latter)
    # ie. raise DelayRequirement if any entry has a prior status
    # do not consider terminal states:
    # prescreen_excluded, not_available, excluded

    # TODO: distingusih rev_status, md_status, pdf_status

    if 'md_imported' == min_status_requirement:
        # Note: md_status=retrieved should not happen
        if len(db.entries) == 0:
            print('No search results available for import.')
            raise DelayRequirement

    if not DELAY_AUTOMATED_PROCESSING:
        return False

    cur_rev_status = [x.get('rev_status', 'NA') for x in db.entries]
    cur_md_status = [x.get('md_status', 'NA') for x in db.entries]
    cur_pdf_status = [x.get('pdf_status', 'NA') for x in db.entries]

    prior_md_status = ['retrieved', 'imported', 'needs_manual_preparation']
    if 'md_prepared' == min_status_requirement:
        if any(x in cur_md_status for x in prior_md_status):
            print('\nTo completed the preparation step, use \n'
                  ' review_template man-prep\n\n')
            raise DelayRequirement

    prior_md_status.append('prepared')
    prior_md_status.append('needs_manual_merging')
    if 'md_processed' == min_status_requirement:
        if any(x in cur_md_status for x in prior_md_status):
            print('\nTo complete the  removal step, use \n'
                  ' review_template man-dedupe\n\n')
            raise DelayRequirement

    prior_md_status.append('processed')
    if 'prescreen_inclusion' == min_status_requirement:
        if any(x in cur_md_status for x in prior_md_status):
            print('\nTo complete the processing, use \n'
                  ' review_template process\n\n')
            raise DelayRequirement

    prior_rev_status = ['retrieved']
    if 'pdf_needs_retrieval' == min_status_requirement:
        if any(x in cur_md_status for x in prior_md_status) or \
                any(x in cur_rev_status for x in prior_rev_status):
            print('\nTo completed the prescreen, use \n'
                  ' review_template prescreen\n\n')
            raise DelayRequirement

    prior_pdf_status = ['needs_retrieval']
    prior_pdf_status.append('needs_manual_retrieval')
    # Note: it's ok if PDFs a re "not_available"
    if 'pdf_imported' == min_status_requirement:
        if any(x in cur_pdf_status for x in prior_pdf_status) or \
                any(x in cur_rev_status for x in prior_rev_status):
            print('\nTo completed the PDF retrieval step, use \n'
                  ' review_template prescreen\n\n')
            raise DelayRequirement

    prior_pdf_status.append('imported')
    prior_pdf_status.append('pdf_needs_manual_preparation')
    if 'prescreened_and_pdf_prepared' == min_status_requirement:
        if any(x in cur_pdf_status for x in prior_pdf_status) or \
                any(x in cur_rev_status for x in prior_rev_status):
            raise DelayRequirement

    # prior_rev_status.append('prescreen_included')

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

        db = pdf_prepare.prepare_pdfs(db, repo)

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
