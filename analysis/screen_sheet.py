#! /usr/bin/env python
import csv
import logging
import os

import entry_hash_function
import pandas as pd
import yaml

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0


with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


def generate_screen_csv(exclusion_criteria):
    data = []

    screen = pd.DataFrame(
        data, columns=[
            'citation_key',
            'inclusion_1',
            'inclusion_2',
        ] + exclusion_criteria + ['comment'],
    )

    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(
        SCREEN, index=False,
        quoting=csv.QUOTE_ALL, na_rep='NA',
    )
    return


def update_screen(bib_database):
    if not os.path.exists(SCREEN):
        generate_screen_csv([])
        # Note: Users can include exclusion criteria afterwards

    screen = pd.read_csv(SCREEN, dtype=str)
    screened_records = screen['citation_key'].tolist()
    to_add = [entry['ID'] for entry in bib_database.entries
              if 'processed' == entry['status'] and
              entry['ID'] not in screened_records]
    for paper_to_screen in to_add:
        add_entry = pd.DataFrame({
            'citation_key': [paper_to_screen],
            'inclusion_1': ['TODO'],
            'inclusion_2': ['TODO'],
        })
        add_entry = add_entry.reindex(
            columns=screen.columns, fill_value='TODO',
        )
        add_entry['comment'] = '-'

        screen = pd.concat([screen, add_entry], axis=0, ignore_index=True)
    # To reformat/sort the screen:
    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(
        SCREEN, index=False,
        quoting=csv.QUOTE_ALL, na_rep='NA',
    )

    return


def append_to_screen(entry):
    with open(SCREEN, 'a') as fd:
        fd.write('"' + entry['ID'] + '","TODO","TODO",""\n')
        # Note: pandas read/write takes too long/may create conflicts!
    return
