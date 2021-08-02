#! /usr/bin/env python
import csv
import logging

import entry_hash_function
import pandas as pd
import utils
import yaml

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

nr_entries_added = 0
nr_current_entries = 0


with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']


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


def generate_screen():
    global nr_entries_added

    print('Creating ' + SCREEN)
    exclusion_criteria = input(
        'Please provide a list of exclusion criteria ' +
        '[criterion1,criterion2,...]: ',
    )

    if exclusion_criteria == '':
        exclusion_criteria = []
    else:
        exclusion_criteria = exclusion_criteria.strip('[]')\
            .replace(' ', '_')\
            .split(',')
        exclusion_criteria = [
            'ec_' + criterion for criterion in exclusion_criteria
        ]

    # Exclusion criteria should be unique
    assert len(exclusion_criteria) == len(set(exclusion_criteria))

    generate_screen_csv(exclusion_criteria)

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )
    for entry in bib_database.get_entry_list():
        nr_entries_added = nr_entries_added + 1

        if 'ID' not in entry:
            print('Error: citation_key not in ' +
                  MAIN_REFERENCES + ' (skipping')
            continue

        update_screen_csv(entry['ID'])

    print('Created ' + SCREEN)
    print('0 records in ' + SCREEN)

    return


def update_screen_csv(paper_to_screen):
    global nr_entries_added

    screen = pd.read_csv(SCREEN, dtype=str)

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
    nr_entries_added = nr_entries_added + 1

    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(
        SCREEN, index=False,
        quoting=csv.QUOTE_ALL, na_rep='NA',
    )

    return


def update_screen():

    print('Loaded existing ' + SCREEN)
    file = open(SCREEN)
    reader = csv.reader(file)
    lines = len(list(reader))-1
    print(str(lines) + ' records in ' + SCREEN)

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )
    bibliography_df = pd.DataFrame.from_dict(bib_database.entries)
    screen = pd.read_csv(SCREEN, dtype=str)

    papers_to_screen = bibliography_df['ID'].tolist()
    screened_papers = screen['citation_key'].tolist()

    papers_no_longer_in_search = [
        x for x in screened_papers if x not in papers_to_screen
    ]
    if len(papers_no_longer_in_search) > 0:
        print(
            'WARNING: papers in ' + SCREEN +
            ' are no longer in ' + MAIN_REFERENCES + ': [',
            ', '.join(papers_no_longer_in_search),
            ']',
        )
        print('note: check and remove the citation_keys/rows from ' + SCREEN)

    for paper_to_screen in papers_to_screen:
        if paper_to_screen not in screened_papers:
            update_screen_csv(paper_to_screen)

    return


if __name__ == '__main__':

    print('')
    print('')

    print('Screen')
    print('TODO: validation to be implemented here')

    print(str(nr_entries_added) + ' records added to ' + SCREEN)
    file = open(SCREEN)
    reader = csv.reader(file)
    lines = len(list(reader))-1
    print(str(lines) + ' records in ' + SCREEN)
    print('')
