#! /usr/bin/env python
import csv
import logging
import os
import sys

import pandas as pd
import yaml

from review_template import entry_hash_function

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)


with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']
DATA_FORMAT = shared_config['params']['DATA_FORMAT']

SCREEN_FILE = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
DATA_FILE = entry_hash_function.paths[HASH_ID_FUNCTION]['DATA']

nr_entries_added = 0
nr_current_entries = 0


def generate_data_pages():

    global nr_entries_added

    print('Data pages')

    # TOOD: possibly include a template that is copied?

    if not os.path.exists('coding'):
        os.mkdir('coding')

    screen = pd.read_csv(SCREEN_FILE, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

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

    print(str(nr_entries_added) + ' records created (coding/citation_key.md)')
    print('')

    return


def get_data_page_missing(DATA_PAGE, records):
    available = []
    with open(DATA_PAGE) as f:
        line = f.read()
        for record in records:
            if record in line:
                available.append(record)

    return list(set(records) - set(available))


def generate_data_page():

    global nr_entries_added

    print('Data page')

    screen = pd.read_csv(SCREEN_FILE, dtype=str)
    screen = screen.drop(screen[screen['inclusion_2'] != 'yes'].index)

    screen = screen['citation_key'].tolist()
    if len(screen) == 0:
        print('no records included yet (SCREEN$inclusion_2 == yes)')
        print()
        sys.exit()

    DATA_PAGE = 'coding.md'
    if not os.path.exists(DATA_PAGE):
        f = open(DATA_PAGE, 'w')
        f.write('# Coding and synthesis\n')
        f.close()

    missing_records = get_data_page_missing(DATA_PAGE, screen)

    if 0 != len(missing_records):
        text_file = open(DATA_PAGE, 'a')
        text_file.write('\n# TODO\n\n- ' + '\n- '.join(missing_records))
        text_file.close()
        nr_entries_added = len(missing_records)

    print(str(nr_entries_added) + ' records created (coding/citation_key.md)')
    print('')

    return


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


def generate_data_sheet():

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

    return


def main():
    print('')
    print('')

    # depending on the template variable:

    if 'NONE' == DATA_FORMAT:
        print('Data extraction format = NONE (change shared_config to start '
              'data extraction)')
    if 'CSV_TABLE' == DATA_FORMAT:
        generate_data_sheet()
    if 'MD_SHEET' == DATA_FORMAT:
        generate_data_page()
    if 'MD_SHEETS' == DATA_FORMAT:
        generate_data_pages()
    if 'MA_VARIABLES_CSV' == DATA_FORMAT:
        print('Not yet implemented: structured data extraction '
              'for meta-analysis')


if __name__ == '__main__':
    main()
