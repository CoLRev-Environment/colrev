#! /usr/bin/env python
import csv
import logging
import os
import sys

import config
import pandas as pd


logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0

SCREEN_FILE = config.paths['SCREEN']
DATA_FILE = config.paths['DATA']


def generate_data_csv(coding_dimensions):
    global nr_entries_added

    screen = pd.read_csv(SCREEN_FILE, dtype=str)

    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    if len(screen) == 0:
        print('no records included yet (SCREEN$inclusion_2 == yes)')
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
    screen.to_csv(DATA_FILE, index=False, quoting=csv.QUOTE_ALL)

    return


def update_data_csv():

    global nr_entries_added

    data = pd.read_csv(DATA_FILE, dtype=str)
    screen = pd.read_csv(SCREEN_FILE, dtype=str)
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
    data.to_csv(DATA_FILE, index=False, quoting=csv.QUOTE_ALL)

    return


if __name__ == '__main__':

    print('')
    print('')

    print('Data')
    print('TODO: validation to be implemented here')

    if not os.path.exists(DATA_FILE):
        print('Creating ' + DATA_FILE)
        coding_dimensions = input(
            'Please provide a list of coding dimensions [dim1,dim2,...]: ',
        )

        coding_dimensions = coding_dimensions.strip('[]')\
                                             .replace(' ', '_')\
                                             .split(',')

        # Coding dimensions should be unique
        assert len(coding_dimensions) == len(set(coding_dimensions))

        generate_data_csv(coding_dimensions)
        print('Created ' + DATA_FILE)
        print('0 records in ' + DATA_FILE)
    else:
        print('Loaded existing ' + DATA_FILE)
        file = open(DATA_FILE)
        reader = csv.reader(file)
        lines = len(list(reader))-1
        print(str(lines) + ' records in ' + DATA_FILE)

        update_data_csv()

    print(str(nr_entries_added) + ' records added to ' + DATA_FILE)
    file = open(DATA_FILE)
    reader = csv.reader(file)
    lines = len(list(reader))-1
    print(str(lines) + ' records in ' + DATA_FILE)
    print('')
