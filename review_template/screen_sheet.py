#! /usr/bin/env python
import configparser
import logging

from review_template import entry_hash_function

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']

SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


def append_to_screen(entry):
    with open(SCREEN, 'a') as fd:
        fd.write('"' + entry['ID'] + '","TODO","TODO",""\n')
        # Note: pandas read/write takes too long/may create conflicts!
    return
