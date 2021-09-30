#! /usr/bin/env python
import logging

import yaml

from review_template import entry_hash_function

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0


with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


def append_to_screen(entry):
    with open(SCREEN, 'a') as fd:
        fd.write('"' + entry['ID'] + '","TODO","TODO",""\n')
        # Note: pandas read/write takes too long/may create conflicts!
    return
