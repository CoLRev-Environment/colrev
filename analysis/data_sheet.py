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


if __name__ == '__main__':

    print('')
    print('')

    print('Data')
    print('TODO: validation to be implemented here')

    screen_file = 'data/screen.csv'
    data_file = 'data/data.csv'

    if not os.path.exists(data_file):
        print('Creating data.csv')
        coding_dimensions = input(
            'Please provide a list of coding dimensions [dim1,dim2,...]: ',
        )

        coding_dimensions = coding_dimensions.strip('[]')\
                                             .replace(' ', '_')\
                                             .split(',')

        # Coding dimensions should be unique
        assert len(coding_dimensions) == len(set(coding_dimensions))

        generate_data_csv(data_file, coding_dimensions, screen_file)
        print('Created data.csv')
        print('0 records in data.csv')
    else:
        print('Loaded existing data.csv')
        file = open(data_file)
        reader = csv.reader(file)
        lines = len(list(reader))-1
        print(str(lines) + ' records in data.csv')

        update_data_csv(data_file, screen_file)

    print(str(nr_entries_added) + ' records added to data.csv')
    file = open(data_file)
    reader = csv.reader(file)
    lines = len(list(reader))-1
    print(str(lines) + ' records in data.csv')
    print('')
