#! /usr/bin/env python
import os
import pprint

import git

from review_template import repo_setup
from review_template import utils

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']


def manual_preparation_commit(r):

    r.index.add([MAIN_REFERENCES])

    hook_skipping = 'false'
    if not repo_setup.config['DEBUG_MODE']:
        hook_skipping = 'true'
    r.index.commit(
        'Prepare manual ' + MAIN_REFERENCES +
        '\n - Using man_prep.py' +
        '\n - ' + utils.get_package_details(),
        author=git.Actor('manual:prepare', ''),
        skip_hooks=hook_skipping
    )
    print(f'Created commit: Prepare manual {MAIN_REFERENCES}')

    return


def man_entry_prep(entry):

    if 'needs_manual_completion' != entry['status']:
        return entry

    pp = pprint.PrettyPrinter(indent=4)

    os.system('cls' if os.name == 'nt' else 'clear')
    pp.pprint(entry)

    return entry


def main():

    r = git.Repo('')
    utils.require_clean_repo(r)

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    print('To implement: prepare manual')

    for entry in bib_database.entries:
        entry = man_entry_prep(entry)
        utils.save_bib_file(bib_database)

    manual_preparation_commit(r)
    return


if __name__ == '__main__':
    main()
