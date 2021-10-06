#! /usr/bin/env python
import configparser
import pprint

from review_template import entry_hash_function
from review_template import importer
from review_template import utils

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']


def main(search_file, id):

    print('Trace search result: ' + search_file + ' - ' + id)

    # TODO: option: trace it through all the history

    search_entries = importer.get_db_with_completion_edits(search_file)
    # No need to check sufficiently_complete metadata:
    # incomplete records should not be merged.
    for entry in search_entries.entries:
        hid = entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)
        entry.update(hash_id=hid)
    target_entry = [x for x in search_entries.entries if id == x['ID']][0]
    bib_database = utils.load_references_bib(
        modification_check=False, initialize=False)

    pp = pprint.PrettyPrinter(indent=4)

    found = False
    for entry in bib_database.entries:
        if entry.get('hash_id', 'NA') == target_entry['hash_id']:
            print('citation_key: ' +
                  entry['ID'] + ' for hash_id ' + entry['hash_id'])
            print()
            # if cleansed (hash_id in data/search/bib_details):
            # add note: quality cleansed entry:
            pp.pprint(entry)
            found = True
    if not found:
        print('Did not find entry')


if __name__ == '__main__':
    main()
