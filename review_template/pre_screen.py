#! /usr/bin/env python
import configparser
import csv
import os
import sys

import git
import pandas as pd

from review_template import entry_hash_function
from review_template import utils

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']

MAIN_REFERENCES = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
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
    return screen


def update_screen(bib_database):

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


def pre_screen_commit():

    r = git.Repo('')
    r.index.add([SCREEN])

    hook_skipping = 'false'
    if not config.getboolean('general', 'DEBUG_MODE'):
        hook_skipping = 'true'

    flag, flag_details = utils.get_version_flags()

    r.index.commit(
        'Pre-screening (manual)' + flag + flag_details +
        '\n - Using pre_screen.py' +
        '\n - ' + utils.get_package_details(),
        author=git.Actor(config['general']['GIT_ACTOR'],
                         config['general']['EMAIL']),
        committer=git.Actor(config['general']['GIT_ACTOR'],
                            config['general']['EMAIL']),
        skip_hooks=hook_skipping
    )

    return


def main():
    print('')
    print('')

    print('Run screen 1')

    # TODO: check prior commits whether duplicates have been removed
    if 'y' != input(
        'Note: start screening only after removing duplicates ' +
        'from ' + MAIN_REFERENCES + '! Proceed with the screen (y/n)?'
    ):
        sys.exit()

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    if not os.path.exists(SCREEN):
        print('Create screen sheet')
        # Note: Users can include exclusion criteria afterwards
        screen = generate_screen_csv(['ec_exclusion_criterion1'])
    else:
        utils.git_modification_check(SCREEN)

    update_screen(bib_database)
    screen = pd.read_csv(SCREEN, dtype=str)

    # Note: this seems to be necessary to ensure that
    # pandas saves quotes around the last column
    screen.comment = screen.comment.fillna('-')

    references = pd.DataFrame.from_dict(bib_database.entries)
    references.rename(columns={'ID': 'citation_key'}, inplace=True)
    req_cols = ['citation_key',
                'author',
                'title',
                'year',
                'journal',
                'volume',
                'number',
                'pages',
                'file',
                'doi',
                ]

    for req_col in req_cols:
        if req_col not in references:
            references[req_col] = ''
    references = references[req_cols]
    references.fillna('', inplace=True)

    # TODO: check if citation_keys in MAIN_REFERENCES and SCREEN are identical?

    print('To stop screening, press ctrl-c')
    try:
        for i, row in screen.iterrows():
            if 'TODO' == row['inclusion_1']:
                inclusion_decision = 'TODO'
                reference = references.loc[
                    references['citation_key'] == row['citation_key']
                ].iloc[0].to_dict()
                while inclusion_decision not in ['y', 'n']:
                    print()
                    print()
                    print(
                        f'{reference["title"]}  -  ',
                        f'{reference["author"]}  ',
                        f'{reference["journal"]}  ',
                        f'{reference["year"]}  (',
                        f'{reference["volume"]}:',
                        f'{reference["number"]}) *',
                        f'{reference["citation_key"]}*',
                    )
                    print()
                    inclusion_decision = input('include (y) or exclude (n)?')
                inclusion_decision = inclusion_decision\
                    .replace('y', 'yes')\
                    .replace('n', 'no')
                screen.at[i, 'inclusion_1'] = inclusion_decision
                if 'no' == inclusion_decision:
                    screen.at[i, 'inclusion_2'] = 'NA'
                    for column in screen.columns:
                        if 'ec_' in column:
                            screen.at[i, column] = 'NA'

                screen.sort_values(by=['citation_key'], inplace=True)
                screen.to_csv(
                    SCREEN, index=False,
                    quoting=csv.QUOTE_ALL, na_rep='NA',
                )
    except KeyboardInterrupt:
        print()
        print()
        print('stopping screen 1')
        print()
        pass

    # If records remain for pre-screening, ask whether to create a commit
    if 0 < screen[screen['inclusion_1'] == 'TODO'].shape[0]:
        if 'y' == input('Create commit (y/n)?'):
            pre_screen_commit()
    else:
        pre_screen_commit()

    return


if __name__ == '__main__':
    main()
