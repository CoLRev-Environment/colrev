#! /usr/bin/env python
import csv
import logging
import os
import sys

import pandas as pd


logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0


def generate_data_csv(data_file, coding_dimensions, screen_filename):
    global nr_entries_added

    screen = pd.read_csv(screen_filename, dtype=str)

    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    if len(screen) == 0:
        print('no records included yet (screen.csv$inclusion_2 == yes)')
        print()
        sys.exit()

    del screen['inclusion_1']
    del screen['inclusion_2']

    for column in screen.columns:
        if column.startswith('ec_'):
            del screen[column]

    del screen['comment']

    for dimension in coding_dimensions:
        screen[dimension] = 'TODO'
    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(data_file, index=False, quoting=csv.QUOTE_ALL)

    return


def update_data_csv(data_file, screen_filename):

    global nr_entries_added

    data = pd.read_csv(data_file, dtype=str)
    screen = pd.read_csv(screen_filename, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    print('TODO: warn when records are no longer included')

    for record_id in screen['citation_key'].tolist():
        # skip when already available
        if 0 < len(data[data['citation_key'].str.startswith(record_id)]):
            continue

        add_entry = pd.DataFrame({'citation_key': [record_id]})

        add_entry = add_entry.reindex(columns=data.columns, fill_value='TODO')

        data = pd.concat([data, add_entry], axis=0, ignore_index=True)

        nr_entries_added = nr_entries_added + 1

    data.sort_values(by=['citation_key'], inplace=True)
    data.to_csv(data_file, index=False, quoting=csv.QUOTE_ALL)

    return


def generate_data_pages(screen_file):

    global nr_entries_added

    screen = pd.read_csv(screen_file, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    print('TODO: warn when records are no longer included')

    screen = screen['citation_key'].tolist()
    if len(screen) == 0:
        print('no records included yet (screen.csv$inclusion_2 == yes)')
        print()
        sys.exit()

    for record_id in screen:
        record_file = 'data/coding/' + record_id + '.md'
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

    screen_file = 'data/screen.csv'

    # TOOD: possibly include a template that is copied?

    if not os.path.exists('data/coding'):
        os.mkdir('data/coding')

    generate_data_pages(screen_file)

    print(str(nr_entries_added) + ' records created (data/citation_key.md)')
    print('')
