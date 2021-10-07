#! /usr/bin/env python
import configparser
import logging
import os
import pprint

from review_template import entry_hash_function
from review_template import importer
from review_template import utils

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']

nr_found = 0


def trace_hash(bibfilename, bib_database, hash_id_needed):
    global nr_found

    pp = pprint.PrettyPrinter(indent=4)

    for entry in bib_database.entries:
        # If there are transformations before the hash is created,
        # they need to be executed before the following.
        if entry.get('hash_id', 'NA') == hash_id_needed:
            print(
                f'\n\n Found hash {hash_id_needed}\n in {bibfilename}\n',
            )
            pp.pprint(entry)
            print('\n')
            nr_found += 1
    return


def main(hash_id_needed):
    global nr_found
    print(f'Trace hash_id: {hash_id_needed}')

    assert len(hash_id_needed) == 64

    bib_files = utils.get_bib_files()
    for bib_file in bib_files:
        print(f'Checking {os.path.basename(bib_file)}')
        search_entries = importer.get_db_with_completion_edits(bib_file)

        # No need to check sufficiently_complete metadata:
        # incomplete records should not be merged.
        for entry in search_entries.entries:
            hid = entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)
            entry.update(hash_id=hid)

        # search_entries = validate_changes.get_search_entries()
        trace_hash(bib_file, search_entries, hash_id_needed)

    if nr_found == 0:
        print('Did not find hash_id')


if __name__ == '__main__':
    main()
