#! /usr/bin/env python
import logging
import os
import sys

import entry_hash_function
import pandas as pd
import yaml


logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)


with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

SCREEN_FILE = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']

nr_entries_added = 0
nr_current_entries = 0


def generate_data_pages():

    global nr_entries_added

    screen = pd.read_csv(SCREEN_FILE, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    print('TODO: warn when records are no longer included')

    screen = screen['citation_key'].tolist()
    if len(screen) == 0:
        print('no records included yet (SCREEN$inclusion_2 == yes)')
        print()
        sys.exit()

    for record_id in screen:
        record_file = 'coding/' + record_id + '.md'
        if not os.path.exists(record_file):
            text_file = open(record_file, 'w')
            text_file.write('')
            text_file.close()
            nr_entries_added += 1

    return


if __name__ == '__main__':

    print('')
    print('')

    print('Data pages')

    # TOOD: possibly include a template that is copied?

    if not os.path.exists('coding'):
        os.mkdir('coding')

    generate_data_pages()

    print(str(nr_entries_added) + ' records created (coding/citation_key.md)')
    print('')
