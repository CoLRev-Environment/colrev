#! /usr/bin/env python
import configparser
import pprint

import git

from review_template import entry_hash_function
from review_template import utils

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']


def manual_preparation_commit():
    r = git.Repo('')
    r.index.add([MAIN_REFERENCES])

    hook_skipping = 'false'
    if not config.getboolean('general', 'DEBUG_MODE'):
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


def main():
    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    print('To implement: prepare manual')
    pp = pprint.PrettyPrinter(indent=4)
    for entry in [x for x in bib_database.entries
                  if 'needs_manual_completion' == x['status']]:
        # Escape sequence to clear terminal output for each new comparison
        print(chr(27) + '[2J')
        pp.pprint(entry)


if __name__ == '__main__':
    main()
