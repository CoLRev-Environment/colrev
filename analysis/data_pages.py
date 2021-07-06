#! /usr/bin/env python
import logging
import os
import sys

import config
import pandas as pd


logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0

SCREEN_FILE = config.paths['SCREEN']


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
